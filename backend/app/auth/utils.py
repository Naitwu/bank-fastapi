import random
import string
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from backend.app.core.config import settings
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()

def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP of specified length."""
    return ''.join(random.choices(string.digits, k=length))

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
    random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=remaining_length))
    username = f"{prefix}-{random_string}"
    return username

def create_activation_token(id: uuid.UUID) -> str:
    """Create a JWT activation token for the given user ID."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACTIVATION_TOKEN_EXPIRE_MINUTES)
    payload = {
        "id": str(id),
        "type": "activation",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token