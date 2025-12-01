from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.logging import get_logger
from backend.app.bank_account.schema import BankAccountReadSchema
from backend.app.api.services.bank_account import activate_bank_account
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.core.services.bank_account_activated_email import send_bank_account_activated_email
from backend.app.core.services.bank_account_created import send_bank_account_created_email
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.auth.schema import RoleCoiceSchema

logger = get_logger()

router = APIRouter(prefix="/bank-account", tags=["Bank Account"])

@router.patch(
    "/activate/{account_id}",
    response_model=BankAccountReadSchema,
    status_code=status.HTTP_200_OK,
    description="Activate a bank account after KYC verification. Only accessible to account executives.",
)
async def activate_bank_account_route(
    account_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> BankAccountReadSchema:
    try:
        if not current_user.role == RoleCoiceSchema.ACCOUNT_EXECUTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to activate bank accounts.",
            )
        activated_account, account_owner = await activate_bank_account(
            account_id=account_id,
            verified_by=current_user.id,
            session=session,
        )
        try:
            if not activated_account.account_number:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Account number missing after activation.",
                )
            await send_bank_account_activated_email(
                email=account_owner.email,
                full_name=account_owner.full_name,
                account_number=activated_account.account_number,
                account_name=activated_account.account_name,
                account_type=activated_account.account_type.value,
                currency=activated_account.currency.value,
            )
            logger.info(f"Sent bank account activated email to user {account_owner.id}")
        except Exception as email_exc:
            logger.error(
                f"Failed to send bank account activated email to user {account_owner.id}: {email_exc}",
                exc_info=True
            )
        logger.info(f"Account {account_id} activated by user {current_user.id}")
        return BankAccountReadSchema.model_validate(activated_account)
    except HTTPException as http_exc:
        logger.warning(
            f"User {current_user.id} failed to activate bank account {account_id}: "
            f"{http_exc.detail.get('message') if isinstance(http_exc.detail, dict) else http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Unexpected error while user {current_user.id} activating bank account {account_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while activating the bank account.",
        )