"""Private SQLite-backed uploads; no image is published without sanitization."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah.database import Store, atomic

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
_lock = atomic
_photos = Store[str, tuple[str, m.Photo]]("photos.photos")
_files = Store[str, bytes]("photos.files", binary=True)
_links = Store[str, set[str]]("photos.links")


def dimensions(data: bytes) -> tuple[int, int]:
    """Read supported format headers; this does not replace full image decoding."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 33:
        if data[8:16] == b"\x00\x00\x00\rIHDR":
            return int.from_bytes(data[16:20], "big"), int.from_bytes(
                data[20:24], "big"
            )
    if data.startswith(b"\xff\xd8"):
        position = 2
        while position + 4 <= len(data):
            if data[position] != 255:
                break
            while position < len(data) and data[position] == 255:
                position += 1
            if position + 3 > len(data):
                break
            marker = data[position]
            position += 1
            if marker in (0xD9, 0xDA):
                break
            size = int.from_bytes(data[position : position + 2], "big")
            if size < 2 or position + size > len(data):
                break
            if (
                marker
                in (
                    0xC0,
                    0xC1,
                    0xC2,
                    0xC3,
                    0xC5,
                    0xC6,
                    0xC7,
                    0xC9,
                    0xCA,
                    0xCB,
                    0xCD,
                    0xCE,
                    0xCF,
                )
                and size >= 8
            ):
                return int.from_bytes(
                    data[position + 5 : position + 7], "big"
                ), int.from_bytes(data[position + 3 : position + 5], "big")
            position += size
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X" and int.from_bytes(data[16:20], "little") == 10:
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(
                data[27:30], "little"
            )
        if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(
                data[28:30], "little"
            ) & 0x3FFF
        if chunk == b"VP8L" and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise HTTPException(422, "INVALID_PHOTO")


def create(user_id: str, data: bytes) -> m.PhotoCreated:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "PHOTO_TOO_LARGE")
    width, height = dimensions(data)
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise HTTPException(422, "INVALID_PHOTO_DIMENSIONS")
    photo_id = f"photo_{uuid4().hex}"
    # Sanitization and privacy processing are unavailable: never expose originals.
    photo = m.Photo(
        id=photo_id,
        status="rejected",
        preview_url=None,
        error_code="PHOTO_PROCESSING_UNAVAILABLE",
    )
    with _lock:
        _photos[photo_id] = (user_id, photo)
        _files[photo_id] = data
    return m.PhotoCreated(
        id=photo_id, status="processing", created_at=datetime.now(UTC)
    )


def get(user: m.User, photo_id: str) -> m.Photo:
    with _lock:
        stored = _photos.get(photo_id)
        if stored is None or (stored[0] != user.id and "moderator" not in user.roles):
            raise HTTPException(404, "NOT_FOUND")
        return stored[1].model_copy(deep=True)


def replace_report_links(user: m.User, report_id: str, photo_ids: list[str]) -> None:
    """Validate ownership and replace references atomically with respect to deletion."""
    with _lock:
        for photo_id in photo_ids:
            stored = _photos.get(photo_id)
            if stored is None or stored[0] != user.id:
                raise HTTPException(404, "NOT_FOUND")
            if stored[1].status == "rejected":
                raise HTTPException(409, "PHOTO_REJECTED")
        for photo_id in _links:
            references = _links[photo_id]
            references.discard(report_id)
            _links[photo_id] = references
        for photo_id in photo_ids:
            _links[photo_id] = _links.get(photo_id, set()) | {report_id}


def delete(user: m.User, photo_id: str) -> None:
    with _lock:
        stored = _photos.get(photo_id)
        if stored is None or stored[0] != user.id:
            raise HTTPException(404, "NOT_FOUND")
        if _links.get(photo_id):
            raise HTTPException(409, "PHOTO_IN_USE")
        del _photos[photo_id]
        del _files[photo_id]
        _links.pop(photo_id, None)
