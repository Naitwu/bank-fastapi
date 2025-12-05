from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import StatementRequestSchema, StatementResponseSchema
from backend.app.api.routes.auth.deps import CurrentUser
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.api.services.transaction import generate_user_statement
from backend.app.core.celery_app import celery_app
from sqlmodel import select
from backend.app.bank_account.models import BankAccount

logger = get_logger()
router = APIRouter(prefix="/bank-account", tags=["Bank Account"])

@router.post(
    "/statement/generate",
    response_model=StatementResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
    description="Generate a bank statement PDF for the current user's bank account within a specified date range.",
)
async def generate_statement_route(
    statement_request: StatementRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> StatementResponseSchema:
    try:
        if statement_request.account_number:
            account_query = select(BankAccount).where(
                BankAccount.account_number == statement_request.account_number,
                BankAccount.user_id == current_user.id,
            )

            result = await session.exec(account_query)
            bank_account = result.first()
            if not bank_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank account not found.",
                )
            if bank_account.account_status != AccountStatusEnum.Active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bank account is not active.",
                )

        result = await generate_user_statement(
            user_id=current_user.id,
            start_date=statement_request.start_date,
            end_date=statement_request.end_date,
            session=session,
            account_number=statement_request.account_number,
        )

        celery_app.AsyncResult(result["task_id"])

        generate_at = datetime.now(timezone.utc)
        expires_at = generate_at + timedelta(hours=1)

        return StatementResponseSchema(
            status="pending",
            message="Statement generation in progress.",
            task_id=result["task_id"],
            statement_id=result["statement_id"],
            generated_at=generate_at,
            expires_at=expires_at,
        )
    except HTTPException as http_exc:
        logger.error(f"HTTP error during statement generation: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Error generating statement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the statement.",
        )

@router.get("/statement/{statement_id}")
async def get_statement_status_route(statement_id: str) -> Response:
    try:
        redis_client = celery_app.backend.client
        pdf_data = redis_client.get(f"statement:{statement_id}")
        if not pdf_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Statement not found or has expired.",
            )
        return Response(content=pdf_data, media_type="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="statement_{statement_id}.pdf"'
        })
    except HTTPException as http_exc:
        logger.error(f"HTTP error retrieving statement: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving statement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the statement.",
        )