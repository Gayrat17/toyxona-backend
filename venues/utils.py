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


def convert_image_field_to_webp(file_field: Any, quality: int = DEFAULT_WEBP_QUALITY) -> None:
    """
    Converts uploaded image files in ImageField or FileField to WEBP format.
    Ignores video files and already webp formatted images.
    """
    if not file_field or not Image:
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

