from uuid import UUID
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlmodel import select
from fastapi import APIRouter, Depends, HTTPException, status, Header
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import TransferRequestSchema, TransferResponseSchema, TransferOTPVerificationSchema
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import initiate_transfer, complete_transfer
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.services.transfer_otp import send_transfer_otp_email
from backend.app.core.services.transfer_alert import send_transfer_alert_email
from backend.app.transaction.models import IdempotencyKey
from backend.app.core.utils.number_format import format_decimal

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

@router.post("/transfer/initiate",
             status_code=status.HTTP_200_OK,
             response_model=TransferResponseSchema,
             description="Initiate a bank account transfer. An OTP will be sent to the user's email for verification."
             )
async def initiate_transfer_route(
    transfer_data: TransferRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(description="A unique UUID4 string to ensure idempotency of the request."),
) -> TransferResponseSchema:
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
                IdempotencyKey.endpoint == "/transfer/initiate",
                IdempotencyKey.expires_at > datetime.now(timezone.utc),
            )
        )
        existing_key = existing_key_result.first()
        if existing_key:
            return TransferResponseSchema(
                status="success",
                message="Retrieved from cache.",
                data=existing_key.response_body
            )

        transaction, sender_account, receiver_account, sender, receiver = await initiate_transfer(
            sender_id=current_user.id,
            sender_account_id=transfer_data.sender_account_id,
            receiver_account_number=transfer_data.receiver_account_number,
            amount=transfer_data.amount,
            description=transfer_data.description,
            security_answer=transfer_data.security_answer,
            session=session,
        )

        try:
            await send_transfer_otp_email(sender.email, sender.otp)
        except Exception as e:
            logger.error(f"Failed to send transfer OTP email: {e}")

        reponse = TransferResponseSchema(
            status="pending",
            message="Transfer initiated. An OTP has been sent to your email for verification.",
            data={
                "transfer_reference": transaction.reference,
                "amount": format_decimal(transfer_data.amount),
                "converted_amount": (
                    transaction.transaction_metadata.get("converted_amount", "N/A") if transaction.transaction_metadata else "N/A"
                ),
                "from_currency": (
                    transaction.transaction_metadata.get("from_currency", "N/A") if transaction.transaction_metadata else "N/A"
                ),
                "to_currency": (
                    transaction.transaction_metadata.get("to_currency", "N/A") if transaction.transaction_metadata else "N/A"
                ),
            }
        )

        idempotency_record = IdempotencyKey(
            key=idempotency_key,
            user_id=current_user.id,
            endpoint="/transfer/initiate",
            response_code=status.HTTP_202_ACCEPTED,
            response_body=reponse.model_dump(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )

        session.add(idempotency_record)
        await session.commit()
        return reponse

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error initiating transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while initiating the transfer."
        )

@router.post(
    "/transfer/complete",
    status_code=status.HTTP_200_OK,
    response_model=TransferResponseSchema,
    description="Complete a bank account transfer by verifying the OTP sent to the user's email."
)
async def complete_transfer_route(
    verification_data: TransferOTPVerificationSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> TransferResponseSchema:
    try:
        transaction, sender_account, receiver_account, sender, receiver = await complete_transfer(
            reference=verification_data.transfer_reference,
            otp=verification_data.otp,
            session=session,
        )

        try:
            await send_transfer_alert_email(
                sender_email=sender.email,
                receiver_email=receiver.email,
                sender_name=sender.full_name,
                receiver_name=receiver.full_name,
                sender_account_number=sender_account.account_number or "Unknown",
                receiver_account_number=receiver_account.account_number or "Unknown",
                amount=transaction.amount,
                converted_amount=(
                    Decimal(
                        transaction.transaction_metadata.get("converted_amount", "0")
                    ) if transaction.transaction_metadata else Decimal("0")
                ),
                sender_currency=sender_account.currency,
                receiver_currency=receiver_account.currency,
                exchange_rate=(
                    Decimal(
                        transaction.transaction_metadata.get("exchange_rate", "1")
                    ) if transaction.transaction_metadata else Decimal("1")
                ),
                conversion_fee=(
                    Decimal(
                        transaction.transaction_metadata.get("conversion_fee", "0")
                    ) if transaction.transaction_metadata else Decimal("0")
                ),
                description=transaction.description,
                reference=transaction.reference,
                transfer_date=transaction.completed_at or transaction.created_at,
                sender_balance=Decimal(sender_account.balance),
                receiver_balance=Decimal(receiver_account.balance),
            )
        except Exception as e:
            logger.error(f"Failed to send transfer alert email: {e}")

        return TransferResponseSchema(
            status="success",
            message="Transfer completed successfully.",
            data={
                "transfer_reference": transaction.reference,
                "amount": format_decimal(str(transaction.amount)),
                "converted_amount": (
                    transaction.transaction_metadata.get("converted_amount", "N/A") if transaction.transaction_metadata else "N/A"
                ),
                "from_currency": (
                    transaction.transaction_metadata.get("from_currency", "N/A") if transaction.transaction_metadata else "N/A"
                ),
                "to_currency": (
                    transaction.transaction_metadata.get("to_currency", "N/A") if transaction.transaction_metadata else "N/A"
                ),
            }
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error completing transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while completing the transfer."
        )