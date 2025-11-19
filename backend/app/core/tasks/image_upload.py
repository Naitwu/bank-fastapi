from typing import TypedDict
import uuid
import cloudinary
import cloudinary.uploader
from backend.app.core.config import settings
from backend.app.core.celery_app import celery_app
from backend.app.core.logging import get_logger

logger = get_logger()


class UploadResponse(TypedDict):
    public_id: str
    url: str
    thumbnail_url: str | None
    type: str


@celery_app.task(
    name="upload_profile_image_task",
    bind=True,
    max_retries=3,
    soft_time_limit=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
)
def upload_profile_image_task(
    self, file_data: bytes, image_type: str, user_id: str, content_type: str
) -> UploadResponse:
    try:
        logger.info(
            f"Starting image upload for user_id: {user_id}, image_type: {image_type}"
        )
        if content_type not in settings.ALLOWED_MINE_TYPES:
            logger.error(f"Invalid image type: {content_type} for user_id: {user_id}")
            raise ValueError(f"Invalid image type: {content_type}")

        file_size_mb = len(file_data) / (1024 * 1024)
        max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
        if file_size_mb > max_size_mb:
            logger.error(
                f"File size {file_size_mb:.2f} MB exceeds limit of {max_size_mb:.2f} MB for user_id: {user_id}"
            )
            raise ValueError(f"File size exceeds limit of {max_size_mb:.2f} MB")

        upload_options = {
            "resource_type": "image",
            "folder": f"{settings.CLOUDINARY_CLOUD_NAME}/profiles/{user_id}",
            "public_id": f"{image_type}_{uuid.uuid4()}",
            "overwrite": True,
            "allowed_formats": ["jpg", "jpeg", "png"],
            "eager": [
                {"width": 800, "height": 800, "crop": "limit"},
                {
                    "width": 200,
                    "height": 200,
                    "crop": "fill",
                },
            ],
            "tags": [f"user_{user_id}", image_type],
            "quality": "auto:good",
            "fetch_format": "auto",
        }

        logger.debug(f"Uploading image with options: {upload_options}")

        result = cloudinary.uploader.upload(
            file_data,
            **upload_options,
        )

        logger.debug(f"Cloudinary upload result: {result}")

        if not result.get("secure_url"):
            logger.error(
                f"Upload succeeded but no secure_url returned for user_id: {user_id}, image_type: {image_type}"
            )
            raise Exception("Upload succeeded but no secure_url returned")

        response: UploadResponse = {
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "thumbnail_url": (
                result.get("eager", [{}])[1].get("secure_url")
                if len(result.get("eager", [])) > 1
                else None
            ),
            "type": image_type,
        }

        for key in ["public_id", "url", "type"]:
            if not response[key]:
                logger.error(
                    f"Missing expected key '{key}' in upload response for user_id: {user_id}, image_type: {image_type}"
                )
                raise Exception(f"Missing expected key '{key}' in upload response")
        logger.info(
            f"Image uploaded successfully for user_id: {user_id}, image_type: {image_type}"
            f"URL: {response['url']}"
            f"Thumbnail URL: {response.get('thumbnail_url', "No thumbnail")}"
            f"Public ID: {response['public_id']}"
        )
        return response

    except ValueError as ve:
        logger.error(
            f"Validation error during image upload for user_id: {user_id}, error: {ve}"
        )
        raise ve
    except Exception as e:
        attempt = self.request.retries + 1
        logger.error(
            f"Error uploading image for user_id: {user_id}, image_type: {image_type}, attempt: {attempt}/{self.max_retries + 1}, error: {e}"
        )
        if attempt > self.max_retries:
            logger.error(
                f"Max retries reached for user_id: {user_id}, image_type: {image_type}. Failing task."
            )
        raise self.retry(exc=e)
