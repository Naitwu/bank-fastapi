from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.schema import ProfileUpdateSchema
from backend.app.user_profile.models import Profile
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import update_user_profile

logger = get_logger()

router = APIRouter(
    prefix="/profile",
    tags=["User Profile"],
)
@router.put("/update", response_model=Profile, status_code=status.HTTP_200_OK)
async def update_profile(
    profile_data: ProfileUpdateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Profile:
    updated_profile = await update_user_profile(current_user.id, profile_data, session)
    logger.info(f"Profile updated for user_id {current_user.id}")
    return updated_profile