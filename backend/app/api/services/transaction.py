import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from backend.app.bank_account.models import BankAccount
from backend.app.transaction.models import Transaction
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.utils import calculate_conversion
from backend.app.transaction.enums import (
    TransactionTypeEnum,
    TransactionCategoryEnum,
    TransactionStatusEnum,
    TransactionFailureReasonEnum,
)
from backend.app.transaction.utils import mark_transaction_failed
from backend.app.transaction.models import Transaction
from backend.app.auth.utils import generate_otp
from backend.app.core.config import settings
from backend.app.auth.models import User
from backend.app.core.logging import get_logger

logger = get_logger()


async def process_deposit(
    *,
    amount: Decimal,
    account_id: uuid.UUID,
    teller_id: uuid.UUID,
    description: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, User]:
    try:
        statement = (
            select(BankAccount, User).join(User).where(BankAccount.id == account_id)
        )
        result = await session.exec(statement)
        account_user = result.first()
        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank account not found.",
            )
        account, account_owner = account_user

        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deposit to an inactive bank account.",
            )
        reference = f"DEP{uuid.uuid4().hex[:8].upper()}"

        balance_before = Decimal(str(account.balance))
        balance_after = balance_before + amount

        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Deposit,
            transaction_category=TransactionCategoryEnum.Credit,
            balance_before=balance_before,
            balance_after=balance_after,
            receiver_account_id=account.id,
            receiver_id=account_owner.id,
            processed_by_id=teller_id,
            transaction_metadata={
                "currency": account.currency,
                "account_number": account.account_number,
            },
        )

        teller = await session.get(User, teller_id)
        if teller:
            if transaction.transaction_metadata is None:
                transaction.transaction_metadata = {}
            transaction.transaction_metadata["teller_name"] = teller.full_name
            transaction.transaction_metadata["teller_email"] = teller.email

        account.balance = float(balance_after)

        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)

        session.add(transaction)
        session.add(account)
        await session.commit()
        await session.refresh(transaction)
        await session.refresh(account)
        return transaction, account, account_owner
    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error processing deposit: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error processing deposit: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the deposit. Please try again later.",
        )


async def initiate_transfer(
    *,
    sender_id: uuid.UUID,
    sender_account_id: uuid.UUID,
    receiver_account_number: str,
    amount: Decimal,
    description: str,
    security_answer: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, BankAccount, User, User]:
    try:
        reciever_account_result = await session.exec(
            select(BankAccount).where(
                BankAccount.account_number == receiver_account_number,
                BankAccount.user_id == sender_id,
            )
        )
        receiver_account = reciever_account_result.first()
        if receiver_account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot transfer to your own account.",
            )

        sender_stmt = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.id == sender_account_id, BankAccount.user_id == sender_id
            )
        )
        sender_result = await session.exec(sender_stmt)
        sender_account_user = sender_result.first()
        if not sender_account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sender bank account not found.",
            )

        sender_account, sender_user = sender_account_user

        if sender_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sender bank account is not active.",
            )

        if security_answer != sender_user.security_answer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security answer is incorrect.",
            )

        receiver_stmt = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.account_number == receiver_account_number)
        )
        receiver_result = await session.exec(receiver_stmt)
        receiver_account_user = receiver_result.first()
        if not receiver_account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receiver bank account not found.",
            )
        receiver_account, receiver_user = receiver_account_user

        if receiver_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Receiver bank account is not active.",
            )

        if Decimal(str(sender_account.balance)) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance in sender's account.",
            )

        try:
            if sender_account.currency != receiver_account.currency:
                converted_amount, exchange_rate, conversion_fee = calculate_conversion(
                    amount=amount,
                    from_currency=sender_account.currency,
                    to_currency=receiver_account.currency,
                )
            else:
                converted_amount = amount
                exchange_rate = Decimal("1.00")
                conversion_fee = Decimal("0.00")

        except Exception as conv_exc:
            logger.error(f"Currency conversion failed: {conv_exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Currency conversion failed. Please try again later.",
            )
        reference = f"TRF{uuid.uuid4().hex[:8].upper()}"
        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Transfer,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Pending,
            balance_before=Decimal(str(sender_account.balance)),
            balance_after=Decimal(str(sender_account.balance)) - amount,
            sender_account_id=sender_account.id,
            sender_id=sender_user.id,
            receiver_account_id=receiver_account.id,
            receiver_id=receiver_user.id,
            transaction_metadata={
                "exchange_rate": str(exchange_rate),
                "conversion_fee": str(conversion_fee),
                "original_amount": str(amount),
                "converted_amount": str(converted_amount),
                "from_currency": sender_account.currency,
                "to_currency": receiver_account.currency,
            },
        )

        otp = generate_otp()

        sender_user.otp = otp
        sender_user.otp_expiry_time = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRATION_MINUTES
        )

        session.add(transaction)
        session.add(sender_user)
        await session.commit()
        await session.refresh(transaction)
        return transaction, sender_account, receiver_account, sender_user, receiver_user

    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error initiating transfer: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error initiating transfer: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while initiating the transfer. Please try again later.",
        )


async def complete_transfer(
    *,
    reference: str,
    otp: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, BankAccount, User, User]:
    try:
        stmt = select(Transaction).where(
            Transaction.reference == reference,
            Transaction.transaction_type == TransactionTypeEnum.Transfer,
            Transaction.status == TransactionStatusEnum.Pending,
        )
        result = await session.exec(stmt)
        transaction = result.first()
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer transaction not found or already processed.",
            )

        sender_account = await session.get(BankAccount, transaction.sender_account_id)
        receiver_account = await session.get(
            BankAccount, transaction.receiver_account_id
        )
        sender_user = await session.get(User, transaction.sender_id)
        receiver_user = await session.get(User, transaction.receiver_id)

        if not all([sender_account, receiver_account, sender_user, receiver_user]):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.INVALID_ACCOUNT,
                details={
                    "sender_account_found": bool(sender_account),
                    "receiver_account_found": bool(receiver_account),
                    "sender_user_found": bool(sender_user),
                    "receiver_user_found": bool(receiver_user),
                },
                session=session,
                error_message="One or more associated accounts or users not found.",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated accounts or users not found.",
            )
        if not sender_user or not sender_user.otp or sender_user.otp != otp:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.INVALID_OTP,
                details={"provided_otp": otp},
                session=session,
                error_message="Invalid OTP provided.",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTP provided.",
            )
        if (
            not sender_user.otp_expiry_time
            or sender_user.otp_expiry_time < datetime.now(timezone.utc)
        ):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.OTP_EXPIRED,
                details={
                    "expiry_time": (
                        sender_user.otp_expiry_time.isoformat()
                        if sender_user.otp_expiry_time
                        else None
                    ),
                    "current_time": datetime.now(timezone.utc).isoformat(),
                },
                session=session,
                error_message="OTP has expired.",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OTP has expired.",
            )

        if sender_account and sender_account.account_status != AccountStatusEnum.Active:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.ACCOUNT_INACTIVE,
                details={"account_id": str(sender_account.id)},
                session=session,
                error_message="Sender account is inactive.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sender bank account is not active.",
            )

        if (
            receiver_account
            and receiver_account.account_status != AccountStatusEnum.Active
        ):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.ACCOUNT_INACTIVE,
                details={"account_id": str(receiver_account.id)},
                session=session,
                error_message="Receiver account is inactive.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Receiver bank account is not active.",
            )

        if not sender_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sender bank account not found.",
            )

        if not receiver_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receiver bank account not found.",
            )

        if Decimal(str(sender_account.balance)) < transaction.amount:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.INSUFFICIENT_BALANCE,
                details={
                    "available_balance": str(sender_account.balance),
                    "required_amount": str(transaction.amount),
                    "shortfall": str(
                        transaction.amount - Decimal(str(sender_account.balance))
                    ),
                },
                session=session,
                error_message="Insufficient balance in sender's account.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance in sender's account.",
            )

        if not transaction.transaction_metadata:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.SYSTEM_ERROR,
                details={"error": "Missing transaction metadata."},
                session=session,
                error_message="System error: Transaction metadata is missing.",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System error occurred. Please try again later.",
            )

        converted_amount_str = transaction.transaction_metadata.get("converted_amount")
        if not converted_amount_str:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.SYSTEM_ERROR,
                details={"error": "Missing converted amount in transaction metadata."},
                session=session,
                error_message="System error: Converted amount is missing.",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System error occurred. Please try again later.",
            )

        try:
            converted_amount = Decimal(converted_amount_str)
        except (TypeError, ValueError) as dec_exc:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.SYSTEM_ERROR,
                details={"error": f"Invalid converted amount format: {dec_exc}"},
                session=session,
                error_message="System error: Invalid converted amount format.",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System error occurred. Please try again later.",
            )

        sender_account.balance = float(
            Decimal(str(sender_account.balance)) - transaction.amount
        )

        receiver_account.balance = float(
            Decimal(str(receiver_account.balance)) + converted_amount
        )

        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)
        sender_user.otp = ""
        sender_user.otp_expiry_time = None
        session.add(transaction)
        session.add(sender_account)
        session.add(receiver_account)
        session.add(sender_user)
        await session.commit()
        await session.refresh(transaction)
        await session.refresh(sender_account)
        await session.refresh(receiver_account)
        await session.refresh(sender_user)
        await session.refresh(receiver_user)

        if not receiver_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receiver user not found.",
            )

        return transaction, sender_account, receiver_account, sender_user, receiver_user

    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error completing transfer: {http_exc.detail}", exc_info=True)
        raise http_exc

    except Exception as exc:
        if transaction:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReasonEnum.SYSTEM_ERROR,
                details={"error": str(exc)},
                session=session,
                error_message="Unexpected system error during transfer completion.",
            )
        await session.rollback()
        logger.error(f"Unexpected error completing transfer: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while completing the transfer. Please try again later.",
        )


async def process_withdrawal(
    *,
    account_number: str,
    amount: Decimal,
    username: str,
    description: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, User]:
    try:
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.account_number == account_number, User.username == username
            )
        )
        result = await session.exec(statement)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank account or user not found.",
            )

        account, account_owner = account_user
        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot withdraw from an inactive bank account.",
            )

        if Decimal(str(account.balance)) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance in the bank account.",
            )

        reference = f"WTH{uuid.uuid4().hex[:8].upper()}"

        balance_before = Decimal(str(account.balance))
        balance_after = balance_before - amount

        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Withdrawal,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Completed,
            balance_before=balance_before,
            balance_after=balance_after,
            sender_account_id=account.id,
            sender_id=account_owner.id,
            completed_at=datetime.now(timezone.utc),
            transaction_metadata={
                "currency": account.currency,
                "account_number": account.account_number,
                "withdrawal_method": "cash",
            },
        )

        account.balance = float(balance_after)
        session.add(transaction)
        session.add(account)
        await session.commit()
        await session.refresh(transaction)
        await session.refresh(account)

        return transaction, account, account_owner

    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error processing withdrawal: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error processing withdrawal: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the withdrawal. Please try again later.",
        )
