from PIL import Image, UnidentifiedImageError
import io
from typing import Tuple
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()


def validate_image(file_data: bytes) -> Tuple[bool, str]:
    file_size_mb = len(file_data) / (1024 * 1024)
    try:
        file_size_mb = len(file_data) / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE:
            return (
                False,
                f"File size exceeds the maximum limit of {settings.MAX_FILE_SIZE} MB.",
            )

        image_buffer = io.BytesIO(file_data)
        with Image.open(image_buffer) as img:
            if img.format is None or img.format.lower() not in ["jpeg", "png", "jpg"]:
                return False, "Unsupported image format."
            width, height = img.size
            if width > settings.MAX_DIMENSIONS or height > settings.MAX_DIMENSIONS:
                return (
                    False,
                    f"Image dimensions exceed the maximum limit of {settings.MAX_DIMENSIONS}px.",
                )

            try:
                img.load()
            except Exception as e:
                logger.error(f"Image loading error: {e}")
                return False, f"Invalid or corrupted image file: {e}"
        return True, "Image is valid."
    except UnidentifiedImageError:
        return False, "The file is not a valid image."
    except Exception as e:
        logger.error(f"Unexpected error during image validation: {e}")
        return False, f"An unexpected error occurred: {e}"
