from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.schema import ProfileCreateSchema
from backend.app.user_profile.models import Profile
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import create_user_profile

logger = get_logger()

router = APIRouter(
    prefix="/profile",
)

@router.post("/create", response_model=ProfileCreateSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_data: ProfileCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Profile:
    new_profile = await create_user_profile(current_user.id, profile_data, session)
    logger.info(f"Profile created for user_id {current_user.id}")
    return new_profile