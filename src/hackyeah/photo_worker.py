"""Durable pending records, with CPU analysis isolated behind a hard timeout."""

import logging
import multiprocessing
import os
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from threading import Event, Thread

from hackyeah import missions, photos, reports
from hackyeah.database import atomic

logger = logging.getLogger(__name__)
TIMEOUT_MESSAGE = (
    "Analiza przekroczyła limit czasu lub została przerwana. Wyślij zdjęcie ponownie."
)


def _dispatch(kind: str, identifier: str) -> bool:
    (photos.process if kind == "photo" else reports.process)(identifier)
    return True


def _child(connection: Connection) -> None:
    while True:
        kind, identifier = connection.recv()
        try:
            connection.send(_dispatch(kind, identifier))
        except Exception:
            logger.exception("Analysis failed for %s", identifier)
            connection.send(False)


class Analyzer:
    def __init__(self, stopped: Event, timeout: float):
        self.stopped = stopped
        self.timeout = timeout
        self.connection: Connection | None = None
        self.process: BaseProcess | None = None

    def close(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1)
            self.process.close()
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def run(self, kind: str, identifier: str) -> bool:
        if self.stopped.is_set():
            return False
        try:
            if self.connection is None:
                context = multiprocessing.get_context("spawn")
                parent, child = context.Pipe()
                self.connection = parent
                self.process = context.Process(
                    target=_child, args=(child,), daemon=True
                )
                self.process.start()
                child.close()
            self.connection.send((kind, identifier))
            deadline = time.monotonic() + self.timeout
            while not self.stopped.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self.connection.poll(min(remaining, 0.25)):
                    result = bool(self.connection.recv())
                    if not result:
                        self.close()
                    return result
        except (EOFError, OSError):
            logger.exception("Analysis process stopped for %s", identifier)
        self.close()
        return False


def process_once(run: Callable[[str, str], bool] = _dispatch) -> None:
    # ponytail: one API worker; use a dedicated queue before deploying multiple API processes.
    for report in reports._reports.values():
        if (
            report.ai_status == "pending"
            and missions.linked_progress(report.id) is not None
            and not run("report", report.id)
        ):
            reports.fail_processing(report, TIMEOUT_MESSAGE)

    pending = [
        photo for _, photo in photos._photos.values() if photo.status == "processing"
    ]
    for photo in pending:
        if photos._mission_verification.get(photo.id, False) and not photos._links.get(
            photo.id, set()
        ):
            continue
        if not run("photo", photo.id):
            with atomic:
                stored = photos._photos.get(photo.id)
                if stored is not None and stored[1] == photo:
                    photo.status = "rejected"
                    photo.error_code = "PHOTO_ANALYSIS_TIMEOUT"
                    photo.description = TIMEOUT_MESSAGE
                    photos._photos[photo.id] = (stored[0], photo)
                    photos._pending_path(photo.id).unlink(missing_ok=True)
                    photos._file_path(photo.id).unlink(missing_ok=True)
                    photos._mission_verification.pop(photo.id, None)
    for report in reports._reports.values():
        if report.ai_status != "pending":
            continue
        if any(
            photos._photos[identifier][1].status == "processing"
            for identifier in report.photo_ids
        ):
            continue
        if not run("report", report.id):
            reports.fail_processing(report, TIMEOUT_MESSAGE)


def start() -> tuple[Event, Thread]:
    stopped = Event()
    timeout = float(os.environ.get("PHOTO_ANALYSIS_TIMEOUT_SECONDS", "120"))
    if not 1 <= timeout <= 600:
        raise ValueError("PHOTO_ANALYSIS_TIMEOUT_SECONDS must be between 1 and 600")

    def accept_missions() -> None:
        while not stopped.wait(0.25):
            try:
                reports.accept_due_missions()
            except Exception:
                logger.exception("Automatic mission acceptance failed")

    acceptance = Thread(target=accept_missions, name="mission-acceptance", daemon=True)

    def run() -> None:
        analyzer = Analyzer(stopped, timeout)

        def analyze(kind: str, identifier: str) -> bool:
            completed = analyzer.run(kind, identifier)
            # Shutdown leaves durable pending work for the next start.
            return completed or stopped.is_set()

        try:
            while not stopped.is_set():
                try:
                    process_once(analyze)
                except Exception:
                    logger.exception("Background photo processing failed")
                stopped.wait(1)
        finally:
            analyzer.close()
            acceptance.join(timeout=1)

    worker = Thread(target=run, name="photo-analysis", daemon=True)
    acceptance.start()
    worker.start()
    return stopped, worker
