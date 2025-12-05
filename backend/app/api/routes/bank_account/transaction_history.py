from fastapi import APIRouter, Depends, HTTPException, status, Query
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import PaginatedTransactionHistoryResponseSchema, TransactionHistoryResponseSchema, TransactionFilterParamsSchema
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import get_user_transactions
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session

logger = get_logger()

router = APIRouter(prefix="/bank-account", tags=["Bank Account"])

@router.get(
    "/transaction-history",
    response_model=PaginatedTransactionHistoryResponseSchema,
    status_code=status.HTTP_200_OK,
    description="Retrieve the transaction history for the current user's bank accounts with optional filters.",
)
async def transaction_history_route(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    filters: TransactionFilterParamsSchema = Depends(),
) -> PaginatedTransactionHistoryResponseSchema:
    try:
        transactions, total = await get_user_transactions(
            user_id=current_user.id,
            session=session,
            skip=skip,
            limit=limit,
            start_date=filters.start_date,
            end_date=filters.end_date,
            transaction_category=filters.transaction_category,
            transaction_type=filters.transaction_type,
            transaction_status=filters.transaction_status,
            min_amount=filters.min_amount,
            max_amount=filters.max_amount,
        )
        transaction_responses = []

        for transaction in transactions:
            metadata = transaction.transaction_metadata or {}

            response = TransactionHistoryResponseSchema(
                id=transaction.id,
                reference=transaction.reference,
                amount=transaction.amount,
                description=transaction.description,
                transaction_type=transaction.transaction_type,
                transaction_category=transaction.transaction_category,
                transaction_status=transaction.status,
                created_at=transaction.created_at,
                completed_at=transaction.completed_at,
                balance_after=transaction.balance_after,
                currency=metadata.get("currency"),
                converted_amount=metadata.get("converted_amount"),
                from_currency=metadata.get("from_currency"),
                to_currency=metadata.get("to_currency"),
                counterparty_account=metadata.get("counterparty_account"),
                counterparty_name=metadata.get("counterparty_name"),
            )
            transaction_responses.append(response)

        return PaginatedTransactionHistoryResponseSchema(
            total=total,
            skip=skip,
            limit=limit,
            transactions=transaction_responses,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving transaction history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving transaction history.",
        )