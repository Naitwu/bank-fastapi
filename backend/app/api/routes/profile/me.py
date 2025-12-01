from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.schema import ProfileResponseSchema
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import get_user_with_profile

logger = get_logger()

router = APIRouter(
    prefix="/profile",
    tags=["User Profile"],
)


@router.get("/me", response_model=ProfileResponseSchema, status_code=status.HTTP_200_OK)
async def get_my_profile(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> ProfileResponseSchema:
    try:
        user = await get_user_with_profile(current_user.id, session)
        response = ProfileResponseSchema(
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            email=user.email or "",
            id_no=str(user.id_no) if user.id_no is not None else "",
            role=user.role,
            profile=user.profile,
        )
        logger.debug(f"Fetched profile for user_id {current_user.id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile for user_id {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while fetching the user profile.",
            },
        )
