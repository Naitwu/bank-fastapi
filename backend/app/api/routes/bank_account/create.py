from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.logging import get_logger
from backend.app.bank_account.schema import BankAccountCreateSchema, BankAccountReadSchema
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.bank_account import create_bank_account
from backend.app.core.services.bank_account_created import send_bank_account_created_email
from  sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session

logger = get_logger()

router = APIRouter(prefix="/bank-account", tags=["Bank Account"])

@router.post("/create",
             response_model=BankAccountReadSchema,
             status_code=status.HTTP_201_CREATED,
             description="Create a new bank account for the current user. Requires completed profile and at least one next of kin. Maximum 3 accounts per user."
             )
async def create_bank_account_route(
    account_data: BankAccountCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> BankAccountReadSchema:
    try:
        new_account = await create_bank_account(
            user_id=current_user.id,
            account_data=account_data,
            session=session,
        )
        try:
            if not new_account.account_number:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Account number generation failed.",
                )
            await send_bank_account_created_email(
                email=current_user.email,
                full_name=current_user.full_name,
                account_number=new_account.account_number,
                account_name=new_account.account_name,
                account_type=new_account.account_type.value,
                currency=new_account.currency.value,
            )
        except Exception as email_exc:
            logger.error(
                f"Failed to send bank account created email to user {current_user.id}: {email_exc}",
                exc_info=True
            )

        logger.info(f"User {current_user.id} created a new bank account: {new_account.account_number}")
        return BankAccountReadSchema.model_validate(new_account)
    except HTTPException as http_exc:
        logger.warning(
            f"User {current_user.id} failed to create bank account: "
            f"{http_exc.detail.get('message') if isinstance(http_exc.detail, dict) else http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Unexpected error while user {current_user.id} creating bank account: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )