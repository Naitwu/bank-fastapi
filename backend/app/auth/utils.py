import random
import string
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from backend.app.core.config import settings
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Response

_ph = PasswordHasher()


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP of specified length."""
    return "".join(random.choices(string.digits, k=length))


def generate_hashed_password(plain_password: str) -> str:
    """Hash a plain text password using Argon2."""
    return _ph.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def generate_username() -> str:
    """Generate a unique username based on the site name and random characters."""
    bank_name = settings.SITE_NAME
    words = bank_name.split()
    prefix = "".join([word[0] for word in words]).upper()
    remaining_length = 12 - len(prefix) - 1
    random_string = "".join(
        random.choices(string.ascii_uppercase + string.digits, k=remaining_length)
    )
    username = f"{prefix}-{random_string}"
    return username


def create_activation_token(id: uuid.UUID) -> str:
    """Create a JWT activation token for the given user ID."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACTIVATION_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "id": str(id),
        "type": "activation",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token


def create_jwt_token(id: uuid.UUID, type: str = settings.COOKIE_ACCESS_NAME) -> str:
    """Create a JWT token for the given user ID."""
    if type == settings.COOKIE_ACCESS_NAME:
        expire_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRATION_MINUTES)
    else:
        expire_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRATION_DAYS)

    payload = {
        "id": str(id),
        "type": type,
        "exp": datetime.now(timezone.utc) + expire_delta,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str | None = None,
) -> None:
    """Set authentication cookies in the response."""
    cookie_settings = {
        "path": settings.COOKIE_PATH,
        "secure": settings.COOKIE_SECURE,
        "httponly": settings.COOKIE_HTTP_ONLY,
        "samesite": settings.COOKIE_SAMESITE,
    }

    access_token_expires = cookie_settings.copy()
    access_token_expires["max_age"] = settings.JWT_ACCESS_TOKEN_EXPIRATION_MINUTES * 60
    response.set_cookie(
        settings.COOKIE_ACCESS_NAME,
        access_token,
        **access_token_expires,
    )

    if refresh_token:
        refresh_token_expires = cookie_settings.copy()
        refresh_token_expires["max_age"] = (
            settings.JWT_REFRESH_TOKEN_EXPIRATION_DAYS * 24 * 60 * 60
        )
        response.set_cookie(
            settings.COOKIE_REFRESH_NAME,
            refresh_token,
            **refresh_token_expires,
        )

    logged_in_cookie_settings = cookie_settings.copy()
    logged_in_cookie_settings["max_age"] = (
        settings.JWT_ACCESS_TOKEN_EXPIRATION_MINUTES * 60
    )
    logged_in_cookie_settings["httponly"] = False
    response.set_cookie(
        settings.COOKIE_LOGGED_IN_NAME,
        "true",
        **logged_in_cookie_settings,
    )

def delete_auth_cookies(response: Response) -> None:
    """Delete authentication cookies from the response."""
    cookies = [
        settings.COOKIE_ACCESS_NAME,
        settings.COOKIE_REFRESH_NAME,
        settings.COOKIE_LOGGED_IN_NAME,
    ]
    for cookie in cookies:
        response.delete_cookie(cookie)