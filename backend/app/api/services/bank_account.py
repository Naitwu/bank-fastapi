import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from backend.app.bank_account.models import BankAccount
from backend.app.bank_account.schema import BankAccountCreateSchema
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.utils import generate_account_number
from backend.app.core.config import settings
from backend.app.auth.models import User
from backend.app.core.logging import get_logger

logger = get_logger()

async def get_primary_bank_account_by_user_id(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> BankAccount | None:
    statement = select(BankAccount).where(BankAccount.user_id == user_id, BankAccount.is_primary == True)
    result = await session.exec(statement)
    return result.first()

async def validate_user_kyc(user: User) -> bool:
    if not user.profile:
        return False
    if not user.next_of_kins or len(user.next_of_kins) == 0:
        return False
    return True

async def create_bank_account(
        user_id: uuid.UUID,
        account_data: BankAccountCreateSchema,
        session: AsyncSession,
)-> BankAccount:
    try:
        statement = select(User).where(User.id == user_id)
        result = await session.exec(statement)
        user = result.first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        await session.refresh(user, ["profile", "next_of_kins"])

        if not await validate_user_kyc(user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "User KYC not completed. Please complete your profile and next of kin information before creating a bank account."},
            )

        statement = select(BankAccount).where(BankAccount.user_id == user_id)
        result = await session.exec(statement)
        existing_accounts = result.all()

        if len(existing_accounts) >= settings.MAX_BANK_ACCOUNTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": f"Maximum number of bank accounts ({settings.MAX_BANK_ACCOUNTS}) reached."},
            )
        if account_data.is_primary:
            primary_existing = any(acc.is_primary for acc in existing_accounts)
            if primary_existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": "Primary bank account already exists."},
                )
        elif len(existing_accounts) == 0:
            account_data.is_primary = True
        account_number = generate_account_number(account_data.currency)
        new_account = BankAccount(
            **account_data.model_dump(exclude={"account_number"}),
            user_id=user_id,
            account_number=account_number,
        )
        session.add(new_account)
        await session.commit()
        await session.refresh(new_account)
        return new_account
    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error creating bank account: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error creating bank account: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the bank account. Please try again later.",
        )

async def activate_bank_account(
    account_id: uuid.UUID,
    verified_by: uuid.UUID,
    session: AsyncSession,
) -> tuple[BankAccount, User]:
    try:
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.id == account_id, BankAccount.user_id != verified_by)
        )
        result = await session.exec(statement)
        account_user_tuple = result.first()
        if not account_user_tuple:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank account not found or cannot activate own account.",
            )
        account, user = account_user_tuple
        if account.account_status == AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bank account is already active.",
            )
        account.kyc_submitted = True
        account.kyc_verified = True
        account.kyc_verified_on = datetime.now(timezone.utc)
        account.kyc_verified_by = verified_by
        account.account_status = AccountStatusEnum.Active
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return account, user
    except HTTPException as http_exc:
        await session.rollback()
        logger.error(f"Error activating bank account: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as exc:
        await session.rollback()
        logger.error(f"Unexpected error activating bank account: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while activating the bank account. Please try again later.",
        )