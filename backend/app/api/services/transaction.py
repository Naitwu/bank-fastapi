import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from backend.app.bank_account.models import BankAccount
from backend.app.transaction.models import Transaction
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.transaction.enums import TransactionTypeEnum, TransactionCategoryEnum, TransactionStatusEnum
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
)-> tuple[Transaction, BankAccount, User]:
    try:
        statement = select(BankAccount, User).join(User).where(BankAccount.id == account_id)
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
            }
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