import asyncio
import jwt
import uuid
import fastapi
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.auth.schema import UserCreateSchema, AccountStatusSchema
from backend.app.auth.models import User
from backend.app.auth.utils import (
    generate_hashed_password,
    generate_username,
    create_activation_token,
    verify_password,
    generate_otp,
)
from datetime import datetime, timezone, timedelta
from backend.app.core.config import settings
from backend.app.core.services.activation_email import send_activation_email
from backend.app.core.services.login_otp import send_login_otp_email
from backend.app.core.services.account_lockout import send_account_lockout_email
from backend.app.core.logging import get_logger

logger = get_logger()


class UserAuthService:
    async def get_user_by_email(
        self,
        email: str,
        session: AsyncSession,
        include_inactive: bool = False,
    ) -> User | None:
        statement = select(User).where(User.email == email)
        if not include_inactive:
            statement = statement.where(User.is_active == True)
        result = await session.exec(statement)
        user = result.first()
        return user

    async def get_user_by_id(
        self,
        user_id: uuid.UUID,
        session: AsyncSession,
        include_inactive: bool = False,
    ) -> User | None:
        statement = select(User).where(User.id == user_id)
        if not include_inactive:
            statement = statement.where(User.is_active == True)
        result = await session.exec(statement)
        user = result.first()
        return user

    async def get_user_by_id_no(
        self,
        id_no: int,
        session: AsyncSession,
        include_inactive: bool = False,
    ) -> User | None:
        statement = select(User).where(User.id_no == id_no)
        if not include_inactive:
            statement = statement.where(User.is_active == True)
        result = await session.exec(statement)
        user = result.first()
        return user

    async def check_user_email_exists(self, email: str, session: AsyncSession) -> bool:
        user = await self.get_user_by_email(email, session)
        return user is not None

    async def check_user_id_no_exists(self, id_no: int, session: AsyncSession) -> bool:
        user = await self.get_user_by_id_no(id_no, session)
        return user is not None

    async def verify_user_credentials(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        return verify_password(plain_password, hashed_password)

    async def reset_user_state(
        self,
        user: User,
        session: AsyncSession,
        *,
        clear_otp: bool = True,
        log_action: bool = True,
    ) -> None:
        previous_status = user.account_status

        user.failed_login_attempts = 0
        user.last_failed_login = None

        if clear_otp:
            user.otp = ""
            user.otp_expiry_time = None

        if user.account_status == AccountStatusSchema.LOCKED:
            user.account_status = AccountStatusSchema.ACTIVE

        await session.commit()
        await session.refresh(user)

        if log_action and previous_status != user.account_status:
            logger.info(
                f"User {user.email} account status changed from {previous_status} -> {user.account_status}"
            )

    async def validate_user_status(self, user: User) -> None:
        if not user.is_active:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Inactive user. Please activate your account.",
                    "action": "Check your email for the activation link.",
                },
            )
        if user.account_status == AccountStatusSchema.LOCKED:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Account locked due to multiple failed login attempts.",
                    "action": "Contact support to unlock your account.",
                },
            )
        if user.account_status == AccountStatusSchema.INACTIVE:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Account is inactive. Please activate your account.",
                    "action": "Check your email for the activation link.",
                },
            )

    async def generate_and_save_otp(
        self,
        user: User,
        session: AsyncSession,
    ) -> tuple[bool, str]:
        try:
            otp = generate_otp()
            otp_expiry = datetime.now(timezone.utc) + timedelta(
                minutes=settings.OTP_EXPIRATION_MINUTES
            )
            user.otp = otp
            user.otp_expiry_time = otp_expiry
            await session.commit()
            await session.refresh(user)
            for attempt in range(3):
                try:
                    await send_login_otp_email(user.email, otp)
                    logger.info(f"Sent login OTP email to {user.email}")
                    return True, otp
                except Exception as e:
                    logger.error(
                        f"Attempt {attempt + 1}: Failed to send OTP email to {user.email}: {e}"
                    )
                    if attempt == 2:
                        user.otp = ""
                        user.otp_expiry_time = None
                        await session.commit()
                        await session.refresh(user)
                        return False, ""
                    await asyncio.sleep(2**attempt)  # Exponential backoff
            return False, ""
        except Exception as e:
            logger.error(f"Error generating/saving OTP for user {user.email}: {e}")
            user.otp = ""
            user.otp_expiry_time = None
            await session.commit()
            await session.refresh(user)
            return False, ""

    async def create_user(
        self,
        user_data: UserCreateSchema,
        session: AsyncSession,
    ) -> User:
        user_data_dict = user_data.model_dump(
            exclude={
                "confirm_password",
                "username",
                "is_active",
                "account_status",
            }
        )
        password = user_data_dict.pop("password")

        new_user = User(
            **user_data_dict,
            username=generate_username(),
            hashed_password=generate_hashed_password(password),
            is_active=False,
            account_status=AccountStatusSchema.PENDING,
        )
        session.add(new_user)
        await session.flush()  # 只 flush，不 commit，這樣可以獲取 id 但保持事務未提交
        await session.refresh(new_user)

        activation_token = create_activation_token(new_user.id)
        try:
            await send_activation_email(new_user.email, activation_token)
            logger.info(f"Sent activation email to {new_user.email}")
        except Exception as e:
            logger.error(f"Failed to send activation email to {new_user.email}: {e}")
            raise

        # 只有在 email 發送成功後才 commit
        await session.commit()
        await session.refresh(new_user)
        return new_user

    async def activate_user_account(
        self,
        token: str,
        session: AsyncSession,
    ) -> User:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            if payload.get("type") != "activation":
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Invalid activation token.",
                        "action": "Please request a new activation email.",
                    },
                )
            user_id = uuid.UUID(payload.get("id"))
        except jwt.ExpiredSignatureError:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Activation token has expired.",
                    "action": "Please request a new activation email.",
                },
            )
        except (jwt.InvalidTokenError, Exception):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Invalid activation token.",
                    "action": "Please request a new activation email.",
                },
            )

        user = await self.get_user_by_id(user_id, session, include_inactive=True)
        if not user:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "User not found.",
                    "action": "Please register for an account.",
                },
            )

        # Check if user is already activated
        if user.is_active and user.account_status == AccountStatusSchema.ACTIVE:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Account is already activated.",
                    "action": "Please log in to your account.",
                },
            )

        await self.reset_user_state(user, session, clear_otp=True, log_action=True)
        user.is_active = True
        user.account_status = AccountStatusSchema.ACTIVE

        await session.commit()
        await session.refresh(user)
        return user

    async def verify_login_otp(
        self,
        email: str,
        otp: str,
        session: AsyncSession,
    ) -> User:
        try:
            user = await self.get_user_by_email(email, session)
            if not user:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_404_NOT_FOUND,
                    detail={
                        "status": "error",
                        "message": "User not found.",
                        "action": "Please register for an account.",
                    },
                )
            await self.validate_user_status(user)
            await self.check_user_lockout(user, session)

            if not user.otp or user.otp != otp:
                await self.increment_failed_login_attempts(user, session)
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Invalid OTP.",
                        "action": "Please check the OTP and try again.",
                    },
                )
            if user.otp_expiry_time is None or user.otp_expiry_time < datetime.now(
                timezone.utc
            ):
                await self.increment_failed_login_attempts(user, session)
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "OTP has expired.",
                        "action": "Please request a new OTP.",
                    },
                )
            await self.reset_user_state(user, session, clear_otp=False)
            return user
        except fastapi.HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying OTP for {email}: {e}")
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "status": "error",
                    "message": "Internal server error.",
                    "action": "Please try again later.",
                },
            )

    async def check_user_lockout(
        self,
        user: User,
        session: AsyncSession,
    ) -> None:
        if user.account_status != AccountStatusSchema.LOCKED:
            return
        if user.last_failed_login is None:
            return

        lockout_time = user.last_failed_login + timedelta(
            minutes=settings.LOCKOUT_DURATION_MINUTES
        )

        current_time = datetime.now(timezone.utc)

        if current_time >= lockout_time:
            await self.reset_user_state(user, session, clear_otp=False)
            logger.info(f"User {user.email} account unlocked after lockout period.")
            return

        remaining_lockout = int((lockout_time - current_time).total_seconds() // 60) + 1
        logger.warning(
            f"User {user.email} attempted login during lockout. {remaining_lockout} minutes remaining."
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": f"Account is locked. Try again in {remaining_lockout} minutes.",
                "action": f"Please try again after {remaining_lockout} minutes.",
                "lockout_remaining_minutes": remaining_lockout,
            },
        )

    async def increment_failed_login_attempts(
        self,
        user: User,
        session: AsyncSession,
    ) -> None:
        user.failed_login_attempts += 1

        current_time = datetime.now(timezone.utc)
        user.last_failed_login = current_time

        if user.failed_login_attempts >= settings.LOGIN_ATTEMPTS:
            user.account_status = AccountStatusSchema.LOCKED
            try:
                await send_account_lockout_email(user.email, current_time)
                logger.info(f"Sent account lockout email to {user.email} successfully.")
            except Exception as e:
                logger.error(
                    f"Failed to send account lockout email to {user.email}: {e}"
                )

            logger.warning(
                f"User {user.email} account locked due to too many failed login attempts."
            )

        await session.commit()
        await session.refresh(user)


user_auth_service = UserAuthService()
