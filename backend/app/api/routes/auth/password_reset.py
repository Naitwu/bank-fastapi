from fastapi import APIRouter, HTTPException, status, Depends, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.auth.schema import PasswordResetConfirmSchema,PasswordResetRequestSchema
from backend.app.api.services.user_auth import user_auth_service
from backend.app.core.services.password_reset import send_password_reset_email
from backend.app.core.config import settings

logger = get_logger()

router = APIRouter(
    prefix="/auth",
)

@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    password_reset_request: PasswordResetRequestSchema,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        user = await user_auth_service.get_user_by_email(email=password_reset_request.email, session=session, include_inactive=True)
        if user:
            await send_password_reset_email(email=user.email, user_id=user.id)
        return {
            "status": "success",
            "message": "If an account exists with the provided email, a password reset link has been sent."
        }
    except Exception as exc:
        logger.error(f"Error during password reset request: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request. Please try again later."
        )

@router.post("/reset-password/{reset_token}", status_code=status.HTTP_200_OK)
async def confirm_password_reset(
    reset_token: str,
    password_reset_confirm: PasswordResetConfirmSchema,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await user_auth_service.reset_password(
            reset_token,
            password_reset_confirm.new_password,
            session,
        )
        return {
            "status": "success",
            "message": "Your password has been successfully reset. You can now log in with your new password."
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        logger.error(f"Error during password reset confirmation: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request. Please try again later."
        )