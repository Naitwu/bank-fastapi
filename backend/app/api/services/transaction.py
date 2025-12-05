from typing import Any
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import desc, func, or_, any_, select

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
from backend.app.core.tasks.statement import generate_statement_pdf

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

async def get_user_transactions(
    user_id: uuid.UUID,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    transaction_type: TransactionTypeEnum | None = None,
    transaction_category: TransactionCategoryEnum | None = None,
    transaction_status: TransactionStatusEnum | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> tuple[list[Transaction], int]:
    try:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date cannot be later than end_date.",
            )
        account_stmt = select(BankAccount.id).where(BankAccount.user_id == user_id)
        account_result = await session.exec(account_stmt)
        account_ids = [account_id for account_id in account_result.all()]
        if not account_ids:
            return [], 0

        base_query = select(Transaction).where(
            or_(
                Transaction.sender_id == user_id,
                Transaction.receiver_id == user_id,
            )
        )
        if start_date:
            base_query = base_query.where(Transaction.created_at >= start_date)
        if end_date:
            base_query = base_query.where(Transaction.created_at <= end_date)
        if transaction_type:
            base_query = base_query.where(Transaction.transaction_type == transaction_type)
        if transaction_category:
            base_query = base_query.where(Transaction.transaction_category == transaction_category)
        if transaction_status:
            base_query = base_query.where(Transaction.status == transaction_status)
        if min_amount:
            base_query = base_query.where(Transaction.amount >= min_amount)
        if max_amount:
            base_query = base_query.where(Transaction.amount <= max_amount)

        base_query = base_query.order_by(desc(Transaction.created_at))

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await session.exec(count_query)
        total = total_result.first() or 0

        transactions = await session.exec(base_query.offset(skip).limit(limit))

        transaction_list = list(transactions.all())

        for transaction in transaction_list:
            await session.refresh(transaction, ["sender", "receiver", "sender_account", "receiver_account"])

            if not transaction.transaction_metadata:
                transaction.transaction_metadata = {}

            if transaction.sender_id == user_id:
                if transaction.receiver:
                    transaction.transaction_metadata["counterparty_name"] = transaction.receiver.full_name
                if transaction.receiver_account:
                    transaction.transaction_metadata["counterparty_account"] = transaction.receiver_account.account_number
            else:
                if transaction.sender:
                    transaction.transaction_metadata["counterparty_name"] = transaction.sender.full_name
                if transaction.sender_account:
                    transaction.transaction_metadata["counterparty_account"] = transaction.sender_account.account_number

        return transaction_list, total
    except HTTPException as http_exc:
        logger.error(f"Error retrieving transactions: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        logger.error(f"Unexpected error retrieving transactions: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving transactions. Please try again later.",
        )

async def get_user_statement_data(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
) -> tuple[dict[str, Any], list[Transaction]]:
    try:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date cannot be later than end_date.",
            )
        user_stmt = select(User).where(User.id == user_id)
        user_result = await session.exec(user_stmt)
        user = user_result.first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        user_info = {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
        }

        txn_stmt = (
            select(Transaction)
            .where(
                or_(
                    Transaction.sender_id == user_id,
                    Transaction.receiver_id == user_id,
                ),
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
            )
            .order_by(desc(Transaction.created_at))
        )

        txn_result = await session.exec(txn_stmt)
        transactions = txn_result.all()

        return user_info, list(transactions)

    except HTTPException as http_exc:
        logger.error(f"Error retrieving statement data: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        logger.error(f"Unexpected error retrieving statement data: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving statement data. Please try again later.",
        )

async def prepare_statement_pdf(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
    account_number: str | None = None,
) -> dict:
    try:
        user_query = select(User).where(User.id == user_id)
        user_result = await session.exec(user_query)
        user = user_result.first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        if account_number:
            account_query = select(BankAccount).where(
                BankAccount.user_id == user_id,
                BankAccount.account_number == account_number,
            )
            account_result = await session.exec(account_query)
            account = account_result.first()
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank account not found.",
                )
            accounts = [account]
        else:
            accounts_query = select(BankAccount).where(BankAccount.user_id == user_id)
            accounts_result = await session.exec(accounts_query)
            accounts = accounts_result.all()
            if not accounts:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No bank accounts found for the user.",
                )

        account_details = []

        for acc in accounts:
            if acc.account_number:
                account_details.append(
                    {
                        "account_number": acc.account_number,
                        "account_name": acc.account_name,
                        "account_type": acc.account_type.value,
                        "currency": acc.currency.value,
                        "balance": str(acc.balance),
                    }
                )

        account_ids = [acc.id for acc in accounts]

        Transactions_query = (
            select(Transaction)
            .where(
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
                Transaction.status == TransactionStatusEnum.Completed,
                or_(
                    Transaction.sender_account_id == any_(account_ids),
                    Transaction.receiver_account_id == any_(account_ids),
                ),
            )
            .order_by(desc(Transaction.created_at))
        )

        transactions_result = await session.exec(Transactions_query)
        transactions = transactions_result.all()

        user_data = {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "accounts": account_details,
        }

        transaction_data = []
        for txn in transactions:
            sender_account = (
                await session.get(BankAccount, txn.sender_account_id)
                if txn.sender_account_id
                else None
            )
            receiver_account = (
                await session.get(BankAccount, txn.receiver_account_id)
                if txn.receiver_account_id
                else None
            )
            transaction_data.append(
                {
                    "reference": txn.reference,
                    "amount": str(txn.amount),
                    "description": txn.description,
                    "created_at": txn.created_at.strftime("%Y-%m-%d"),
                    "transaction_type": txn.transaction_type.value,
                    "transaction_category": txn.transaction_category.value,
                    "balance_after": str(txn.balance_after),
                    "sender_account": sender_account.account_number if sender_account else None,
                    "receiver_account": receiver_account.account_number if receiver_account else None,
                    "metadata": txn.transaction_metadata,
                }
            )
        return {
            "user": user_data,
            "transactions": transaction_data,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "is_single_account": bool(account_number),
        }
    except HTTPException as http_exc:
        logger.error(f"Error preparing statement PDF data: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        logger.error(f"Unexpected error preparing statement PDF data: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while preparing statement data. Please try again later.",
        )

async def generate_user_statement(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
    account_number: str | None = None,
)-> dict:
    try:
        statement_data = await prepare_statement_pdf(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            session=session,
            account_number=account_number,
        )

        statement_id = str(uuid.uuid4())

        task = generate_statement_pdf.delay(
            statement_id=statement_id,
            statement_data=statement_data,
        )

        return {
            "status": "pending",
            "message": "Statement generation in progress.",
            "statement_id": statement_id,
            "task_id": task.id,
        }
    except ValueError as val_err:
        logger.error(f"Value error generating user statement: {val_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Unexpected error generating user statement: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the statement. Please try again later.",
        )