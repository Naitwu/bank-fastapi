from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.logging import get_logger
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import delete_next_of_kin
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from uuid import UUID

logger = get_logger()

router = APIRouter(
    prefix="/next-of-kin",
    tags=["Next of Kin"],
)


@router.delete(
    "/delete/{next_of_kin_id}",
    status_code=status.HTTP_200_OK,
    description="Delete an existing next of kin.",
)
async def delete_next_of_kin_route(
    next_of_kin_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await delete_next_of_kin(
            user_id=current_user.id,
            next_of_kin_id=next_of_kin_id,
            session=session,
        )
        logger.info(f"User {current_user.id} deleted next of kin: {next_of_kin_id}")
        return {
            "status": "success",
            "message": "Next of kin deleted successfully.",
        }
    except HTTPException as http_exc:
        logger.warning(
            f"User {current_user.id} failed to delete next of kin {next_of_kin_id}: "
            f"{http_exc.detail.get('message') if isinstance(http_exc.detail, dict) else http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Unexpected error while user {current_user.id} deleting next of kin {next_of_kin_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )
