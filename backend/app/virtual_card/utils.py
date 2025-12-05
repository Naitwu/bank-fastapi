import secrets
from datetime import datetime, timedelta
from typing import Tuple
from argon2 import PasswordHasher

def generate_visa_card_number() -> str:
    prefix = '4'  # Visa cards start with '4'
    partial_number = prefix + ''.join(secrets.choice('0123456789') for _ in range(14))

    total = 0

    for i, digit in enumerate(partial_number):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n

    check_digit = (10 - (total % 10)) % 10
    return partial_number + str(check_digit)

def generate_cvv() -> tuple[str, str]:
    cvv = ''.join(secrets.choice('0123456789') for _ in range(3))
    ph = PasswordHasher()
    hashed_cvv = ph.hash(cvv)
    return cvv, hashed_cvv

def verify_cvv(cvv: str, hashed_cvv: str) -> bool:
    ph = PasswordHasher()
    try:
        ph.verify(hashed_cvv, cvv)
        return True
    except:
        return False

def generate_card_expiry_date() -> datetime:
    current_date = datetime.now()
    expiry_date = current_date + timedelta(days=3*365)
    if expiry_date.month == 12:
        expiry_date = expiry_date.replace(month=1, year=expiry_date.year + 1, day=1)
    else:
        expiry_date = expiry_date.replace(month=expiry_date.month + 1, day=1)

    expiry_date = expiry_date - timedelta(days=1)
    return expiry_date
