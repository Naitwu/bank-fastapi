from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.auth.schema import AccountStatusSchema, EmailRequestSchema
from backend.app.api.services.user_auth import user_auth_service
from backend.app.core.services.activation_email import send_activation_email
from backend.app.core.config import settings
from backend.app.auth.utils import create_activation_token

logger = get_logger()

router = APIRouter(
    prefix="/auth",
)

@router.get("/activate/{token}", status_code=status.HTTP_200_OK)
async def activate_user(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await user_auth_service.activate_user_account(token, session)
        return {
            "status": "success",
            "message": "Account activated successfully.",
            "user_email": user.email,
        }
    except HTTPException:
        # Re-raise HTTPException from service layer
        raise
    except Exception as e:
        # Handle unexpected errors only
        logger.error(f"Unexpected error during account activation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while activating the account.",
                "action": "Please try again later.",
            },
        )

@router.post(
    "/resend-activation", status_code=status.HTTP_200_OK
)
async def resend_activation_email(
    email_request: EmailRequestSchema,
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await user_auth_service.get_user_by_email(session, email_request.email, include_inactive=True)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "User with this email does not exist.",
                    "action": "Please check the email address and try again.",
                },
            )
        if user.is_active or user.account_status == AccountStatusSchema.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Account is already activated.",
                    "action": "Please log in to your account.",
                },
            )
        token = create_activation_token(user.id)
        await send_activation_email(user.email, token)
        logger.info(f"Resent activation email to: {user.email}")
        return {
            "status": "success",
            "message": "Activation email resent successfully.",
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error resending activation email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while resending the activation email.",
                "action": "Please try again later.",
            },
        )