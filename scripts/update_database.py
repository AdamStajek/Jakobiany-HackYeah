"""Refresh all persisted datasets and atomically publish the resulting SQLite DB."""

import argparse
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def run_script(module: str, *arguments: str) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    print(f"Etap: {module}", flush=True)
    subprocess.run(
        [sys.executable, "-m", module, *arguments], cwd=ROOT, env=env, check=True
    )


def update_database(
    database: Path, *, cached_osm: bool = False, missing_only: bool = False
) -> None:
    database = database.resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    # Advisory lock prevents concurrent runs of this orchestrator.
    import fcntl

    with database.with_suffix(database.suffix + ".update.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if missing_only:
            if not database.exists():
                raise FileNotFoundError(
                    "Tryb uzupełniania wymaga istniejącej bazy miejsc."
                )
            snapshot = ROOT / "data/temporary/construction.json"
            if not snapshot.exists():
                run_script("scripts.scrape_construction", "--output", str(snapshot))
            run_script(
                "scripts.import_temporary_data",
                "--database",
                str(database),
                "--input",
                str(snapshot),
                "--missing-only",
            )
            print(
                "Uzupełniono brakujące remonty; OSM i istniejące rekordy pozostawiono bez zmian.",
                flush=True,
            )
            return
        with TemporaryDirectory(
            dir=database.parent, prefix=".database-update-"
        ) as directory:
            stage = Path(directory)
            candidate = stage / "krakow.sqlite3"
            if database.exists():
                with (
                    closing(
                        sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
                    ) as previous,
                    closing(sqlite3.connect(candidate)) as target,
                ):
                    previous.backup(target)
            run_script("scripts.download_osm", *([] if cached_osm else ["--refresh"]))
            run_script(
                "scripts.scrape_construction",
                "--output",
                str(stage / "construction.json"),
            )
            run_script("scripts.build_places_db", "--database", str(candidate))
            run_script(
                "scripts.import_temporary_data",
                "--database",
                str(candidate),
                "--input",
                str(stage / "construction.json"),
            )
            run_script(
                "scripts.report_places",
                "--database",
                str(candidate),
                "--json-output",
                str(stage / "coverage.json"),
                "--markdown-output",
                str(stage / "osm-coverage.md"),
            )
            with closing(sqlite3.connect(candidate)) as db:
                if (
                    db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                    or db.execute("PRAGMA foreign_key_check").fetchall()
                ):
                    raise ValueError("Nowa baza nie przeszła kontroli spójności.")
            # Keep a SQLite-consistent rollback copy, then publish via same-filesystem rename.
            if database.exists():
                with (
                    closing(
                        sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
                    ) as previous,
                    closing(sqlite3.connect(stage / "backup.sqlite3")) as backup,
                ):
                    previous.backup(backup)
                (stage / "backup.sqlite3").replace(
                    database.with_suffix(".previous.sqlite3")
                )
            candidate.replace(database)
            temporary_dir = ROOT / "data/temporary"
            temporary_dir.mkdir(parents=True, exist_ok=True)
            (stage / "construction.json").replace(temporary_dir / "construction.json")
            (stage / "coverage.json").replace(ROOT / "data/coverage.json")
            (stage / "osm-coverage.md").replace(ROOT / "docs/osm-coverage.md")
    print(
        f"Zaktualizowano {database}. Pogoda jest pobierana w locie przez API.",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    parser.add_argument(
        "--cached-osm",
        action="store_true",
        help="Reuse verified OSM downloads; still refresh construction data.",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Fill absent construction rows from the local snapshot; no OSM rebuild.",
    )
    args = parser.parse_args()
    update_database(
        args.database, cached_osm=args.cached_osm, missing_only=args.missing_only
    )


if __name__ == "__main__":
    main()
