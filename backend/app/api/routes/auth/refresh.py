from fastapi import APIRouter, Cookie, HTTPException, status, Depends, Response
import jwt
import uuid
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.api.services.user_auth import user_auth_service
from backend.app.core.config import settings
from backend.app.auth.utils import create_jwt_token, set_auth_cookies

logger = get_logger()

router = APIRouter(
    prefix="/auth",
)

@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_access_token(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(None, alias=settings.COOKIE_REFRESH_NAME),
) -> dict:
    try:
        # 檢查 refresh token 是否存在
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is missing. Please log in again.",
            )

        # 解碼並驗證 refresh token
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SIGNING_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

            # 驗證 token 類型
            if payload.get("type") != settings.COOKIE_REFRESH_NAME:
                logger.warning("Invalid token type in refresh token.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type. Please log in again.",
                )

            # 提取 user_id
            user_id = payload.get("id")
            if not user_id:
                logger.warning("Missing user ID in refresh token payload.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload. Please log in again.",
                )

        except jwt.ExpiredSignatureError:
            logger.info("Refresh token has expired.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please log in again.",
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid refresh token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token. Please log in again.",
            )

        # 從資料庫獲取用戶
        user = await user_auth_service.get_user_by_id(
            user_id=uuid.UUID(user_id),
            session=session,
        )

        if not user:
            logger.warning(f"User not found for ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found. Please log in again.",
            )

        # 驗證用戶狀態
        await user_auth_service.validate_user_status(user)

        # 生成新的 access token
        new_access_token = create_jwt_token(user.id, type=settings.COOKIE_ACCESS_NAME)

        # 設置新的 access token cookie（保留原有的 refresh token）
        set_auth_cookies(response, new_access_token)

        logger.info(f"Access token refreshed successfully for user: {user.email}")

        return {
            "status": "success",
            "message": "Access token refreshed successfully.",
            "user": {
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "id_no": user.id_no,
                "role": user.role,
            }
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        logger.error(f"Error during token refresh: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while refreshing the token. Please try again later."
        )