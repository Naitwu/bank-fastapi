from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import DepositRequestSchema
from backend.app.transaction.enums import TransactionTypeEnum
from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.auth.schema import RoleCoiceSchema
from backend.app.api.services.transaction import process_deposit
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.services.deposit_alert import send_deposit_alert_email

logger = get_logger()

router = APIRouter(prefix="/bank-account", tags=["Bank Account"])

@router.post("/deposit",
             status_code=status.HTTP_201_CREATED,
             description="Deposit funds into a bank account. Only tellers are authorized to perform this action."
             )
async def deposit_route(
    deposit_data: DepositRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != RoleCoiceSchema.TELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tellers are authorized to perform deposits.",
        )
    try:
        transaction, account, account_owner = await process_deposit(
            amount=deposit_data.amount,
            account_id=deposit_data.account_id,
            teller_id=current_user.id,
            description=deposit_data.description,
            session=session,
        )
        if not account.account_number:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Deposit failed due to missing account number.",
            )
        try:
            currency_value = account.currency.value
            await send_deposit_alert_email(
                email=account_owner.email,
                full_name=account_owner.full_name,
                action=TransactionTypeEnum.Deposit.value,
                amount=transaction.amount,
                account_name=account.account_name,
                account_number=account.account_number,
                currency=currency_value,
                description=transaction.description,
                date=transaction.created_at,
                reference=transaction.reference,
                balance=transaction.balance_after,
            )
        except Exception as e:
            logger.error(f"Failed to send deposit alert email: {e}")
        logger.info(f"Teller {current_user.id} deposited {transaction.amount} to account {account.account_number}")
        return{
            "status": "success",
            "message": "Deposit successful.",
            "data": {
                "transaction_id": str(transaction.id),
                "reference": transaction.reference,
                "amount": str(transaction.amount),
                "balance_after": str(transaction.balance_after),
                "status": transaction.status.value,
            }
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        logger.error(f"Unexpected error during deposit: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the deposit process.",
        )