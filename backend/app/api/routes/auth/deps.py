import jwt
from typing import Annotated
from fastapi import Depends, HTTPException, status, Cookie
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.config import settings
from backend.app.auth.models import User
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger

logger = get_logger()


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    access_token: str | None = Cookie(None, alias=settings.COOKIE_ACCESS_NAME),
) -> User:
    if not access_token:
        logger.warning("No access token provided in cookies.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Not authenticated.",
                "action": "Please login to this resource.",
            },
        )
    try:
        payload = jwt.decode(
            access_token, settings.SIGNING_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != settings.COOKIE_ACCESS_NAME:
            logger.warning("Invalid token type in access token.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Not authenticated.",
                    "action": "Please login to this resource.",
                },
            )
        from backend.app.api.services.user_auth import user_auth_service

        user = await user_auth_service.get_user_by_id(payload.get("id"), session)
        if not user:
            logger.warning(f"User not found for id {payload.get('id')}.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Not authenticated.",
                    "action": "Please login to this resource.",
                },
            )
        await user_auth_service.validate_user_status(user)
        return user

    except jwt.ExpiredSignatureError:
        logger.warning("Access token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Token has expired.",
                "action": "Please login again.",
            },
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid access token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Invalid token.",
                "action": "Please login to this resource.",
            },
        )
    except Exception as e:
        logger.error(f"Error retrieving current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Internal server error.",
                "action": "Please try again later.",
            },
        )


CurrentUser = Annotated[User, Depends(get_current_user)]
