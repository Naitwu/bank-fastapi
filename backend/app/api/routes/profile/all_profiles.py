from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.schema import (
    PaginateddProfileResponseSchema,
    ProfileResponseSchema,
)
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import get_all_user_profiles


logger = get_logger()

router = APIRouter(
    prefix="/profile",
    tags=["User Profiles"],
)


@router.get(
    "/all",
    response_model=PaginateddProfileResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def list_user_profiles(
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1),
    session: AsyncSession = Depends(get_session),
) -> PaginateddProfileResponseSchema:
    try:
        users, total_count = await get_all_user_profiles(
            session, current_user, skip, limit
        )
        profile_responses = [
            ProfileResponseSchema(
                username=user.username or "",
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                email=user.email or "",
                id_no=str(user.id_no) if user.id_no is not None else "",
                role=user.role,
                profile=user.profile,
            ) for user in users
        ]
        response = PaginateddProfileResponseSchema(
            profiles=profile_responses,
            total=total_count,
            skip=skip,
            limit=limit,
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching all user profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while fetching all user profiles.",
            },
        )