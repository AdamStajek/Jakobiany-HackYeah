"""Private SQLite-backed uploads with decoding and metadata removal."""

from datetime import UTC, datetime
from io import BytesIO
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from hackyeah import models as m
from hackyeah.database import Store, atomic

logger = logging.getLogger(__name__)

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
_lock = atomic
_photos = Store[str, tuple[str, m.Photo]]("photos.photos")
_legacy_files = Store[str, bytes]("photos.files", binary=True)
_links = Store[str, set[str]]("photos.links")


def _file_path(photo_id: str) -> Path:
    root = Path(os.environ.get("PHOTO_STORAGE_PATH", database_root() / "photos"))
    return root / f"{photo_id}.png"


def database_root() -> Path:
    from hackyeah.database import database_path

    return database_path().parent


def create(
    user_id: str,
    data: bytes,
    *,
    address: str | None = None,
    metric: str | None = None,
) -> m.PhotoCreated:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "PHOTO_TOO_LARGE")
    try:
        with Image.open(BytesIO(data)) as original:
            if original.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(415, "UNSUPPORTED_MEDIA_TYPE")
            width, height = original.size
            if width < 1 or height < 1 or width * height > MAX_PIXELS:
                raise HTTPException(422, "INVALID_PHOTO_DIMENSIONS")
            original.verify()
        with Image.open(BytesIO(data)) as original:
            image = ImageOps.exif_transpose(original)
            image = image.convert(
                "RGBA"
                if "A" in image.getbands() or "transparency" in image.info
                else "RGB"
            )
            image.info.clear()
            output = BytesIO()
            image.save(output, format="PNG")
            sanitized = output.getvalue()
    except Image.DecompressionBombError as exc:
        raise HTTPException(422, "INVALID_PHOTO_DIMENSIONS") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(422, "INVALID_PHOTO") from exc
    from hackyeah.report_ai import describe_photo

    error_code = None
    try:
        description, sensitive = describe_photo(sanitized)
    except Exception:
        logger.exception("Photo analysis failed; anonymizing the entire image")
        description, sensitive = "Zdjęcie do ręcznej weryfikacji", True
        error_code = "PHOTO_ANALYSIS_UNAVAILABLE"
    if sensitive:
        with Image.open(BytesIO(sanitized)) as image:
            size = image.size
            image = image.convert("RGB")
            image.thumbnail((16, 16))
            image = image.resize(size, Image.Resampling.NEAREST)
            output = BytesIO()
            image.save(output, format="PNG")
            sanitized = output.getvalue()
    photo_id = f"photo_{uuid4().hex}"
    photo = m.Photo(
        id=photo_id,
        status="ready",
        preview_url=f"/api/v1/photos/{photo_id}/content",
        error_code=error_code,
        description=description,
        address=address,
        metric=metric,
    )
    path = _file_path(photo_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(sanitized)
    path.chmod(0o600)
    try:
        with _lock:
            _photos[photo_id] = (user_id, photo)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return m.PhotoCreated(id=photo_id, status="ready", created_at=datetime.now(UTC))


def get(user: m.User, photo_id: str) -> m.Photo:
    with _lock:
        stored = _photos.get(photo_id)
        if stored is None or (stored[0] != user.id and "moderator" not in user.roles):
            raise HTTPException(404, "NOT_FOUND")
        return stored[1].model_copy(deep=True)


def content(user: m.User, photo_id: str) -> bytes:
    with _lock:
        photo = get(user, photo_id)
        if photo.status != "ready":
            raise HTTPException(409, "PHOTO_REJECTED")
        path = _file_path(photo_id)
        return path.read_bytes() if path.exists() else _legacy_files[photo_id]


def owned_contents(user: m.User, photo_ids: list[str]) -> list[bytes]:
    """Read owned images before inference without keeping a transaction open."""
    with _lock:
        for photo_id in photo_ids:
            stored = _photos.get(photo_id)
            if stored is None or stored[0] != user.id:
                raise HTTPException(404, "NOT_FOUND")
        return [content(user, photo_id) for photo_id in photo_ids]


def replace_report_links(user: m.User, report_id: str, photo_ids: list[str]) -> None:
    """Validate ownership and replace references atomically with respect to deletion."""
    with _lock:
        for photo_id in photo_ids:
            stored = _photos.get(photo_id)
            if stored is None or stored[0] != user.id:
                raise HTTPException(404, "NOT_FOUND")
            if stored[1].status != "ready":
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
        _file_path(photo_id).unlink(missing_ok=True)
        if photo_id in _legacy_files:
            del _legacy_files[photo_id]
        _links.pop(photo_id, None)
