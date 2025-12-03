from uuid import UUID
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlmodel import select
from fastapi import APIRouter, Depends, HTTPException, status, Header
from backend.app.core.logging import get_logger
from backend.app.transaction.models import IdempotencyKey
from backend.app.transaction.schema import WithdrawalRequestSchema
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import process_withdrawal
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.services.withdrawal_alert import send_withdrawal_alert_email


logger = get_logger()

router = APIRouter(prefix="/bank-account", tags=["Bank Account"])


def validate_uuid4(value: str) -> str:
    try:
        uuid_obj = UUID(value, version=4)
        if str(uuid_obj) != value.lower():
            raise ValueError("Not a valid UUID4")
        return value
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Idempotency-Key header. Must be a valid UUID4 string.",
        )


@router.post(
    "/withdrawal",
    status_code=status.HTTP_201_CREATED,
    description="Process a bank account withdrawal.",
)
async def withdrawal_route(
    withdrawal_data: WithdrawalRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(
        description="A unique UUID4 string to ensure idempotency of the request."
    ),
):
    try:
        idempotency_key = validate_uuid4(idempotency_key)
        if not idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key header is required.",
            )
        existing_key_result = await session.exec(
            select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.user_id == current_user.id,
                IdempotencyKey.endpoint == "/withdrawal",
                IdempotencyKey.expires_at > datetime.now(timezone.utc),
            )
        )
        existing_key = existing_key_result.first()
        if existing_key:
            return {
                "status": "success",
                "message": "Withdrawal has already been processed. Retrieving existing record.",
                "data": existing_key.response_body,
            }

        transaction, acccount, user = await process_withdrawal(
            account_number=withdrawal_data.account_number,
            amount=withdrawal_data.amount,
            username=withdrawal_data.username,
            description=withdrawal_data.description,
            session=session,
        )

        try:
            await send_withdrawal_alert_email(
                email=user.email,
                full_name=user.full_name,
                amount=transaction.amount,
                account_number=acccount.account_number or "Unknown",
                account_name=acccount.account_name,
                currency=acccount.currency.value,
                description=transaction.description,
                transaction_date=transaction.completed_at or transaction.created_at,
                reference=transaction.reference,
                balance=Decimal(str(acccount.balance)),
            )
        except Exception as e:
            logger.error(f"Failed to send withdrawal alert email: {e}")

        response_body = {
            "status": "success",
            "message": "Withdrawal processed successfully.",
            "data": {
                "transaction_id": str(transaction.id),
                "reference": transaction.reference,
                "amount": str(transaction.amount),
                "balance": str(transaction.balance_after),
                "status": transaction.status,
            },
        }

        idempotency_record = IdempotencyKey(
            key=idempotency_key,
            user_id=user.id,
            endpoint="/withdrawal",
            response_code=status.HTTP_201_CREATED,
            response_body=response_body,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        session.add(idempotency_record)
        await session.commit()
        return response_body

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing withdrawal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the withdrawal.",
        )
