from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.enums import ImageTypeEnum
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import initiate_image_upload, update_profile_image_url
from backend.app.core.utils.image import validate_image
from backend.app.core.celery_app import celery_app

logger = get_logger()

router = APIRouter(
    prefix="/profile",
)


@router.post("/upload/{image_type}", status_code=status.HTTP_202_ACCEPTED)
async def upload_profile_image(
    image_type: ImageTypeEnum,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> dict:
    try:
        file_content = await file.read()
        is_valid, validation_message = validate_image(file_content)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": validation_message,
                },
            )
        task_id = initiate_image_upload(
            file_content=file_content,
            image_type=image_type,
            content_type=file.content_type or "application/octet-stream",
            user_id=current_user.id,
        )
        return {
            "status": "pending",
            "message": "Image upload initiated.",
            "task_id": task_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating image upload for user_id {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while initiating the image upload.",
            },
        )

@router.get("/upload/{task_id}/status", status_code=status.HTTP_200_OK)
async def get_upload_status(
    task_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        task = celery_app.AsyncResult(task_id)
        if task.ready():
            if task.successful():
                result = task.result
                logger.debug(f"Task result: {result}")
                if not isinstance(result, dict):
                    logger.error(f"Unexpected task result type: {type(result)} for task_id: {task_id}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={
                            "status": "error",
                            "message": "Unexpected task result format.",
                        },
                    )
                if not result.get("url") or not result.get("type"):
                    logger.error(f"Missing expected keys in task result for task_id: {task_id}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={
                            "status": "error",
                            "message": "Incomplete task result data.",
                        },
                    )
                await update_profile_image_url(
                    user_id=current_user.id,
                    image_type=ImageTypeEnum(result["type"]),
                    image_url=result["url"],
                    session=session,
                )
                return {
                    "status": "completed",
                    "image_url": result["url"],
                    "thumb_url": result.get("thumbnail_url"),
                    "image_type": result["type"],
                }
            else:
                error = str(task.result) if task.result else "Unknown error"
                return {
                    "status": "failed",
                    "message": f"Image upload failed: {error}",
                }
        else:
            return {
                "status": "pending",
                "message": "Image upload is still in progress.",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking upload status for task_id {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while checking the upload status.",
            },
        )