import logging
from io import BytesIO

import cloudinary
import cloudinary.uploader

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}
MAX_IMAGE_SIZE_MB = 5
MAX_VIDEO_SIZE_MB = 50


def configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def _validate_file(content_type: str, file_size: int, allowed_types: set[str], max_mb: int) -> None:
    if content_type not in allowed_types:
        raise ValueError(f"File type '{content_type}' not allowed. Allowed: {allowed_types}")
    if file_size > max_mb * 1024 * 1024:
        raise ValueError(f"File exceeds maximum size of {max_mb}MB.")


async def upload_image(
    file_bytes: bytes,
    content_type: str,
    folder: str,
    public_id: str | None = None,
) -> dict:
    """Upload image to Cloudinary. Returns url and public_id."""
    _validate_file(content_type, len(file_bytes), ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE_MB)
    configure_cloudinary()
    try:
        result = cloudinary.uploader.upload(
            BytesIO(file_bytes),
            folder=f"gymconnect/{folder}",
            public_id=public_id,
            overwrite=True,
            resource_type="image",
            transformation=[{"quality": "auto", "fetch_format": "auto"}],
        )
        return {"url": result["secure_url"], "public_id": result["public_id"]}
    except Exception as exc:
        logger.error("Cloudinary upload failed: %s", exc)
        raise


async def upload_file(file_bytes: bytes, content_type: str, folder: str = "general") -> str:
    """Generic upload — returns just the URL."""
    result = await upload_image(file_bytes, content_type, folder=folder)
    return result["url"]


async def delete_file(public_id: str, resource_type: str = "image") -> bool:
    configure_cloudinary()
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return result.get("result") == "ok"
    except Exception as exc:
        logger.error("Cloudinary delete failed for %s: %s", public_id, exc)
        return False
