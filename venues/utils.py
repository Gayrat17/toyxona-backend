import io
import os
import logging
from typing import Any, Optional
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    Image = None
    UnidentifiedImageError = Exception

DEFAULT_WEBP_QUALITY: int = 85
SKIP_EXTENSIONS: set[str] = {".webp"}
VIDEO_EXTENSIONS: set[str] = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}
ALLOWED_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXTENSIONS: set[str] = {".mp4", ".webm", ".mov", ".m4v"}
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB


def validate_media_file(file: Any, is_video: bool = False) -> None:
    """
    Validates uploaded file against size limits, extension whitelist,
    and inspects images with PIL to prevent malicious file uploads (e.g. web shells, stored XSS).
    """
    if not file:
        return

    name = getattr(file, "name", "")
    _, ext = os.path.splitext(name)
    ext_lower = ext.lower()

    from rest_framework.exceptions import ValidationError

    if is_video:
        if ext_lower not in ALLOWED_VIDEO_EXTENSIONS:
            raise ValidationError(
                f"Noto'g'ri video formati ({ext}). Ruxsat etilgan: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}."
            )
        if hasattr(file, "size") and file.size > MAX_VIDEO_SIZE_BYTES:
            raise ValidationError("Video hajmi 50 MB dan oshmasligi kerak.")
    else:
        if ext_lower not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError(
                f"Noto'g'ri rasm formati ({ext}). Faqat JPG, PNG yoki WEBP formatidagi rasmlar qabul qilinadi."
            )
        if hasattr(file, "size") and file.size > MAX_IMAGE_SIZE_BYTES:
            raise ValidationError("Rasm hajmi 10 MB dan oshmasligi kerak.")

        if Image:
            try:
                initial_pos = file.tell() if hasattr(file, "tell") else 0
                img = Image.open(file)
                img.verify()
                if hasattr(file, "seek"):
                    file.seek(initial_pos)
            except Exception as exc:
                raise ValidationError("Yuklangan fayl yaroqli rasm emas yoki buzilgan.") from exc


def convert_image_field_to_webp(file_field: Any, quality: int = DEFAULT_WEBP_QUALITY) -> None:
    """
    Converts uploaded image files in ImageField or FileField to WEBP format.
    Ignores video files and already webp formatted images.
    """
    if not file_field or not Image:
        return

    field_name = str(getattr(file_field, "name", ""))
    if field_name.startswith(("http://", "https://")):
        return

    try:
        filename = os.path.basename(file_field.name)
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()

        if ext_lower in SKIP_EXTENSIONS or ext_lower in VIDEO_EXTENSIONS:
            return

        file_field.open()
        img = Image.open(file_field)

        # Convert palette/transparent images properly
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="WEBP", quality=quality)
        output.seek(0)

        name, _ = os.path.splitext(filename)
        new_filename = f"{name}.webp"
        file_field.save(new_filename, ContentFile(output.read()), save=False)

    except (UnidentifiedImageError, OSError, IOError) as e:
        logger.warning(f"Could not convert file '{file_field.name}' to WEBP format: {e}")
    except Exception as e:
        logger.error(f"Unexpected error converting image to WEBP: {e}", exc_info=True)

