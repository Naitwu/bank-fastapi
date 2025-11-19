import uuid
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from backend.app.user_profile.models import Profile
from backend.app.user_profile.schema import ProfileCreateSchema, ProfileUpdateSchema, ImageTypeSchema
from backend.app.core.logging import get_logger
from backend.app.core.tasks.image_upload import upload_profile_image_task

logger = get_logger()


async def get_user_profile(user_id: uuid.UUID, session: AsyncSession) -> Profile | None:
    try:
        statement = select(Profile).where(Profile.user_id == user_id)
        result = await session.exec(statement)
        return result.first()
    except Exception as e:
        logger.error(f"Error fetching user profile for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while fetching the user profile.",
            },
        )


async def create_user_profile(
    user_id: uuid.UUID, profile_data: ProfileCreateSchema, session: AsyncSession
) -> Profile:
    try:
        existing_profile = await get_user_profile(user_id, session)
        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "User profile already exists.",
                },
            )
        new_profile = Profile(user_id=user_id, **profile_data.model_dump())
        session.add(new_profile)
        await session.commit()
        await session.refresh(new_profile)
        logger.info(f"Created new user profile for user_id {user_id}")
        return new_profile
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating user profile for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while creating the user profile.",
            },
        )

async def update_user_profile(
    user_id: uuid.UUID, profile_data: ProfileUpdateSchema, session: AsyncSession
) -> Profile:
    try:
        existing_profile = await get_user_profile(user_id, session)
        if not existing_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "User profile not found.",
                    "action": "create_profile",
                },
            )
        update_data = profile_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key not in["profile_photo_url", "id_photo_url", "signature_photo_url"]:
                setattr(existing_profile, key, value)
        await session.commit()
        await session.refresh(existing_profile)
        logger.info(f"Updated user profile for user_id {user_id}")
        return existing_profile
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating user profile for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while updating the user profile.",
            },
        )

def initiate_image_upload(
        file_content: bytes,
        image_type: ImageTypeSchema,
        content_type: str,
        user_id: uuid.UUID,
) -> str:
    try:
        task = upload_profile_image_task.delay(
            file_content,
            image_type.value,
            str(user_id),
            content_type,
        )
        return task.id
    except Exception as e:
        logger.error(f"Error initiating image upload for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while initiating the image upload.",
            },
        )

async def update_profile_image_url(
    user_id: uuid.UUID,
    image_type: ImageTypeSchema,
    image_url: str,
    session: AsyncSession,
) -> Profile:
    try:
        existing_profile = await get_user_profile(user_id, session)
        if not existing_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "User profile not found.",
                    "action": "create_profile",
                },
            )
        field_map = {
            ImageTypeSchema.PROFILE_PHOTO: "profile_photo_url",
            ImageTypeSchema.ID_PHOTO: "id_photo_url",
            ImageTypeSchema.SIGNATURE_PHOTO: "signature_photo_url",
        }
        field_name = field_map.get(image_type)
        if not field_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Invalid image type.",
                },
            )
        setattr(existing_profile, field_name, image_url)
        await session.commit()
        await session.refresh(existing_profile)
        return existing_profile
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating {image_type.value} URL for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": f"An error occurred while updating the {image_type.value} URL.",
            },
        )
