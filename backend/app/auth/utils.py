import random
import string
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
    bank_name = settings.SITE_NAME
    words = bank_name.split()
    prefix = "".join([word[0] for word in words]).upper()
    remaining_length = 12 - len(prefix) - 1
    random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=remaining_length))
    username = f"{prefix}-{random_string}"
    return username