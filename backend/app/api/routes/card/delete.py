from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.logging import get_logger
from backend.app.api.routes.auth.deps import CurrentUser
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.api.services.card import delete_virtual_card
from backend.app.virtual_card.schema import CardDeleteResponseSchema

logger = get_logger()

router = APIRouter(prefix="/virtual-card", tags=["virtual-card"])

@router.delete(
    "/{card_id}/delete",
    status_code=status.HTTP_200_OK,
    description="Delete a virtual card. Card must have zero balance and no physical card requested.",
    response_model=CardDeleteResponseSchema,
)
async def delete_card_route(
    card_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await delete_virtual_card(
            card_id=card_id,
            user_id=current_user.id,
            session=session,
        )

        return CardDeleteResponseSchema(
            status="success",
            message="Virtual card deleted successfully.",
            deleted_at=result["deleted_at"],
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        logger.error(f"Error deleting virtual card: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the virtual card.",
        )
    