import uuid
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from backend.app.user_profile.models import Profile
from backend.app.user_profile.schema import ProfileCreateSchema, ProfileUpdateSchema
from backend.app.core.logging import get_logger

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