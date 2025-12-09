import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func

from backend.app.virtual_card.models import VirtualCard
from backend.app.bank_account.models import BankAccount
from backend.app.auth.models import User
from backend.app.transaction.models import Transaction
from backend.app.transaction.enums import (
    TransactionCategoryEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from backend.app.virtual_card.enums import VirtualCardStatusEnum
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.auth.schema import RoleCoiceSchema
from backend.app.virtual_card.utils import (
    generate_visa_card_number,
    generate_cvv,
    generate_card_expiry_date,
)
from backend.app.core.logging import get_logger

logger = get_logger()


async def create_virtual_card(
    user_id: uuid.UUID,
    bank_account_id: uuid.UUID,
    card_data: dict,
    session: AsyncSession,
) -> tuple[VirtualCard, User, BankAccount]:
    try:
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.id == bank_account_id,
                BankAccount.user_id == user_id,
            )
        )
        result = await session.exec(statement)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank account not found for the user.",
            )

        bank_account, user = account_user

        if bank_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bank account is not active.",
            )

        card_currency = card_data.get("currency")
        if card_currency != bank_account.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Card currency must match bank account currency.",
            )

        cleaned_data = card_data.copy()
        cleaned_data.pop("card_number", None)
        cleaned_data.pop("card_status", None)
        cleaned_data.pop("is_active", None)
        cleaned_data.pop("cvv_hash", None)
        cleaned_data.pop("available_balance", None)
        cleaned_data.pop("total_topped_up", None)
        cleaned_data.pop("card_metadata", None)

        card_number = generate_visa_card_number()

        if not cleaned_data.get("expiry_date"):
            expiry_date = generate_card_expiry_date()
            cleaned_data["expiry_date"] = expiry_date.date()

        card = VirtualCard(
            **cleaned_data,
            card_number=card_number,
            bank_account_id=bank_account_id,
            card_status=VirtualCardStatusEnum.Pending,
            is_active=True,
            available_balance=0.0,
            total_topped_up=0.0,
            last_top_up_date=datetime.now(timezone.utc),
            card_metadata={
                "created_by": str(user_id),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        session.add(card)
        await session.commit()
        await session.refresh(card)

        return card, user, bank_account
    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error creating virtual card: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error creating virtual card: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the virtual card. Please try again later.",
        )

async def block_virtual_card(
    card_id: uuid.UUID,
    blocked_data: dict,
    blocked_by: uuid.UUID,
    session: AsyncSession,
) -> tuple[VirtualCard, User]:
    try:
        statement = (
            select(VirtualCard, User)
            .select_from(VirtualCard)
            .join(BankAccount)
            .join(User)
            .where(VirtualCard.id == card_id)
        )
        result = await session.exec(statement)
        card_user = result.first()
        if not card_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Virtual card not found.",
            )

        card, card_owner = card_user

        if card.card_status == VirtualCardStatusEnum.Blocked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Virtual card is already blocked.",
            )

        block_time = datetime.now(timezone.utc)
        card.card_status = VirtualCardStatusEnum.Blocked
        card.block_reason = blocked_data.get("block_reason", "No reason provided")
        card.block_reason_description = blocked_data.get("block_reason_description", "")
        card.blocked_by = blocked_by
        card.blocked_at = block_time
        if not card.card_metadata:
            card.card_metadata = {}
        card.card_metadata.update({
            "blocked_at": block_time.isoformat(),
            "blocked_by": str(blocked_by),
            "block_reason": blocked_data["block_reason"].value,
        })

        session.add(card)
        await session.commit()
        await session.refresh(card)

        return card, card_owner
    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error blocking virtual card: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error blocking virtual card: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while blocking the virtual card. Please try again later.",
        )

async def top_up_virtual_card(
    card_id: uuid.UUID,
    account_number: str,
    amount: float,
    description: str,
    session: AsyncSession,
) -> tuple[VirtualCard, Transaction]:
    try:
        statement = (
            select(VirtualCard, BankAccount)
            .join(BankAccount)
            .where(
                VirtualCard.id == card_id,
                BankAccount.account_number == account_number,
            )
        )
        result = await session.exec(statement)
        card_account = result.first()
        if not card_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Virtual card or bank account not found.",
            )

        card, bank_account = card_account

        if card.card_status != VirtualCardStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Virtual card is not active.",
            )

        if bank_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bank account is not active.",
            )

        if Decimal(str(bank_account.account_status)) < Decimal(str(amount)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient funds in bank account.",
            )

        if card.currency != bank_account.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Currency mismatch between virtual card and bank account.",
            )

        reference = f"TOP{uuid.uuid4().hex[:8].upper()}"

        balance_before = Decimal(str(card.available_balance))
        balance_after = balance_before - Decimal(str(amount))

        current_time = datetime.now(timezone.utc)

        transaction = Transaction(
            amount=Decimal(str(amount)),
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Transfer,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Completed,
            balance_before=balance_before,
            balance_after=balance_after,
            sender_account_id=bank_account.id,
            sender_id=bank_account.user_id,
            completed_at=current_time,
            transaction_metadata={
                "top_up_type": "virtual_card",
                "card_id": str(card.id),
                "card_last_four": card.last_four_digits,
                "currency": card.currency,
            },
        )

        bank_account.balance = float(balance_after)
        card.available_balance += amount
        card.total_topped_up += amount
        card.last_top_up_date = current_time

        session.add(transaction)
        session.add(bank_account)
        session.add(card)
        await session.commit()
        await session.refresh(card)
        await session.refresh(transaction)

        return card, transaction
    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error topping up virtual card: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error topping up virtual card: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while topping up the virtual card. Please try again later.",
        )

async def activate_virtual_card(
    card_id: uuid.UUID,
    activated_by: uuid.UUID,
    session: AsyncSession,
) -> tuple[VirtualCard, User, str]:
    try:
        statement = (
            select(VirtualCard, User)
            .select_from(VirtualCard)
            .join(BankAccount)
            .join(User)
            .where(VirtualCard.id == card_id)
        )
        result = await session.exec(statement)
        card_user = result.first()
        if not card_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Virtual card not found.",
            )

        card, card_owner = card_user

        exective = await session.get(User, activated_by)
        if not exective or exective.role != RoleCoiceSchema.ACCOUNT_EXECUTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only account executives can activate virtual cards.",
            )

        if card.card_status == VirtualCardStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Virtual card is already active.",
            )

        new_cvv, cvv_hash = generate_cvv()

        card.card_status = VirtualCardStatusEnum.Active
        card.cvv_hash = cvv_hash

        if not card.card_metadata:
            card.card_metadata = {}
        card.card_metadata.update({
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "activated_by": str(activated_by),
        })

        session.add(card)
        await session.commit()
        await session.refresh(card)

        return card, card_owner, new_cvv

    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error activating virtual card: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error activating virtual card: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while activating the virtual card. Please try again later.",
        )

async def delete_virtual_card(
    card_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    try:
        statement = (
            select(VirtualCard, BankAccount)
            .join(BankAccount)
            .where(
                VirtualCard.id == card_id,
                BankAccount.user_id == user_id,
            )
        )
        result = await session.exec(statement)
        card_account = result.first()
        if not card_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Virtual card not found for the user.",
            )

        card, _ = card_account

        if card.physical_card_requested_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete card with physical card request",
            )

        if card.available_balance > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete card with available balance. Please withdraw the balance before deletion.",
            )

        deletion_time = datetime.now(timezone.utc)

        existing_metadata = card.card_metadata or {}

        new_metadata = {
            **existing_metadata,
            "deleted_at": deletion_time.isoformat(),
            "deletion_reason": "User requested deletion",
            "deleted_by": str(user_id),
            "card_status_before_deletion": card.card_status.value,
            "deletion_timestamp": deletion_time.isoformat(),
        }

        card.card_metadata = new_metadata
        card.card_status = VirtualCardStatusEnum.Inactive
        card.is_active = False

        session.add(card)
        await session.commit()
        await session.refresh(card)

        logger.info(f"Virtual card {card_id} deleted by user {user_id} at {deletion_time.isoformat()}")

        return{
            "status": "success",
            "message": "Virtual card deleted successfully.",
            "deleted_at": deletion_time.isoformat(),
        }
    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error deleting virtual card: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error deleting virtual card: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the virtual card. Please try again later.",
        )
    
