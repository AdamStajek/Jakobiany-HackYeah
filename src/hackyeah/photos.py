"""Private SQLite-backed uploads with decoding and metadata removal."""

import logging
import os
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from hackyeah import models as m
from hackyeah.database import Store, atomic
from hackyeah.photo_privacy import anonymize

logger = logging.getLogger(__name__)

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
_lock = atomic
_photos = Store[str, tuple[str, m.Photo]]("photos.photos")
_legacy_files = Store[str, bytes]("photos.files", binary=True)
_links = Store[str, set[str]]("photos.links")
_mission_verification = Store[str, bool]("photos.mission_verification")


def _file_path(photo_id: str) -> Path:
    root = Path(os.environ.get("PHOTO_STORAGE_PATH", database_root() / "photos"))
    return root / f"{photo_id}.png"


def _pending_path(photo_id: str) -> Path:
    return _file_path(photo_id).with_suffix(".pending.png")


def database_root() -> Path:
    from hackyeah.database import database_path

    return database_path().parent


def create(
    user_id: str,
    data: bytes,
    *,
    address: str | None = None,
    metric: str | None = None,
    mission_verification: bool = False,
    defer_processing: bool = False,
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
            if not defer_processing:
                try:
                    image = anonymize(image)
                except Exception as exc:
                    logger.exception("Photo privacy detection failed")
                    raise HTTPException(503, "PHOTO_ANALYSIS_UNAVAILABLE") from exc
            output = BytesIO()
            image.save(output, format="PNG")
            sanitized = output.getvalue()
    except Image.DecompressionBombError as exc:
        raise HTTPException(422, "INVALID_PHOTO_DIMENSIONS") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(422, "INVALID_PHOTO") from exc
    from hackyeah.report_ai import describe_photo

    error_code = None
    description = "Przetwarzanie zdjęcia"
    if not defer_processing:
        try:
            description, _ = describe_photo(sanitized)
        except Exception:
            logger.exception("Photo description failed")
            description = "Zdjęcie do ręcznej weryfikacji"
            error_code = "PHOTO_ANALYSIS_UNAVAILABLE"
    photo_id = f"photo_{uuid4().hex}"
    photo = m.Photo(
        id=photo_id,
        status="processing" if defer_processing else "ready",
        preview_url=None if defer_processing else f"/api/v1/photos/{photo_id}/content",
        error_code=error_code,
        description=description,
        address=address,
        metric=metric,
    )
    path = _pending_path(photo_id) if defer_processing else _file_path(photo_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(sanitized)
    path.chmod(0o600)
    try:
        with _lock:
            _photos[photo_id] = (user_id, photo)
            if mission_verification:
                _mission_verification[photo_id] = True
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return m.PhotoCreated(
        id=photo_id,
        status="processing" if defer_processing else "ready",
        created_at=datetime.now(UTC),
    )


def process(photo_id: str) -> None:
    """Process the private pending file; never expose an unredacted preview."""
    from hackyeah.report_ai import describe_photo

    with _lock:
        stored = _photos.get(photo_id)
        if stored is None or stored[1].status != "processing":
            return
    photo = stored[1].model_copy(deep=True)
    pending = _pending_path(photo_id)
    try:
        with Image.open(pending) as original:
            image = anonymize(original)
            output = BytesIO()
            image.save(output, format="PNG")
            sanitized = output.getvalue()
        try:
            photo.description, _ = describe_photo(sanitized)
        except Exception:
            logger.exception("Photo description failed for %s", photo_id)
            photo.description = "Zdjęcie do ręcznej weryfikacji"
            photo.error_code = "PHOTO_DESCRIPTION_UNAVAILABLE"
        with _lock:
            if _photos.get(photo_id) != stored:
                return
            path = _file_path(photo_id)
            path.write_bytes(sanitized)
            path.chmod(0o600)
            photo.status = "ready"
            photo.preview_url = f"/api/v1/photos/{photo_id}/content"
            _photos[photo_id] = (stored[0], photo)
            _mission_verification.pop(photo_id, None)
    except Exception:
        logger.exception("Photo processing failed for %s", photo_id)
        with _lock:
            if _photos.get(photo_id) == stored:
                photo.status = "rejected"
                photo.error_code = "PHOTO_ANALYSIS_UNAVAILABLE"
                photo.description = "Nie udało się bezpiecznie przetworzyć zdjęcia"
                _photos[photo_id] = (stored[0], photo)
                _mission_verification.pop(photo_id, None)
                _file_path(photo_id).unlink(missing_ok=True)
    finally:
        pending.unlink(missing_ok=True)


def validate_owned(user: m.User, photo_ids: list[str]) -> list[m.Photo]:
    with _lock:
        items = []
        for photo_id in photo_ids:
            stored = _photos.get(photo_id)
            if stored is None or stored[0] != user.id:
                raise HTTPException(404, "NOT_FOUND")
            items.append(stored[1].model_copy(deep=True))
        return items


def verification_contents(user: m.User, photo_ids: list[str]) -> list[bytes]:
    """Read private pending originals for mission verification only."""
    with _lock:
        images = []
        for photo_id in photo_ids:
            stored = _photos.get(photo_id)
            if stored is None or stored[0] != user.id:
                raise HTTPException(404, "NOT_FOUND")
            photo = stored[1]
            if photo.status == "processing":
                images.append(_pending_path(photo_id).read_bytes())
            elif photo.status == "ready":
                images.append(content(user, photo_id))
            else:
                raise HTTPException(409, "PHOTO_REJECTED")
        return images


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
            if stored[1].status not in {"ready", "processing"}:
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
        _pending_path(photo_id).unlink(missing_ok=True)
        if photo_id in _legacy_files:
            del _legacy_files[photo_id]
        _links.pop(photo_id, None)
        _mission_verification.pop(photo_id, None)
