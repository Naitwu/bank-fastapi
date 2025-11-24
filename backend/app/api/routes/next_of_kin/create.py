from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.logging import get_logger
from backend.app.next_of_kin.schema import NextOfKinCreateSchema, NextOfKinReadSchema
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import create_next_of_kin
from  sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session

logger = get_logger()

router = APIRouter(
    prefix="/next-of-kin",
    tags=["Next of Kin"],
)

@router.post("/create", response_model=NextOfKinReadSchema, status_code=status.HTTP_201_CREATED, description="Create a new next of kin. Maximum 3 per user, only one can be primary contact.")
async def create_next_of_kin_route(
    next_of_kin_data: NextOfKinCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
)-> NextOfKinReadSchema:
    try:
        new_next_of_kin = await create_next_of_kin(
            user_id=current_user.id,
            next_of_kin_data=next_of_kin_data,
            session=session,
        )
        logger.info(f"User {current_user.id} created a new next of kin: {new_next_of_kin.full_name}")
        return new_next_of_kin
    except HTTPException as http_exc:
        logger.warning(
            f"User {current_user.id} failed to create next of kin: "
            f"{http_exc.detail.get('message') if isinstance(http_exc.detail, dict) else http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Unexpected error while user {current_user.id} creating next of kin: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )
