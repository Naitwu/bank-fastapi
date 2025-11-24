from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.logging import get_logger
from backend.app.next_of_kin.schema import  NextOfKinReadSchema
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import get_next_of_kins_by_user
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session

logger = get_logger()

router = APIRouter(
    prefix="/next-of-kin",
    tags=["Next of Kin"],
)

@router.get("/all", response_model=list[NextOfKinReadSchema], status_code=status.HTTP_200_OK, description="Retrieve all next of kin for the current user.")
async def get_all_next_of_kin(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[NextOfKinReadSchema]:
    try:
        next_of_kins = await get_next_of_kins_by_user(current_user.id, session)
        return [NextOfKinReadSchema.model_validate(kin) for kin in next_of_kins]
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving next of kin for user_id {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while retrieving next of kin.",
            },
        )