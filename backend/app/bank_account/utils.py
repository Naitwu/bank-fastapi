import secrets
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
from backend.app.bank_account.enums import AccountCurrencyEnum
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from fastapi import HTTPException, status

logger = get_logger()


def get_currency_code(currency: AccountCurrencyEnum) -> str:
    currency_map = {
        AccountCurrencyEnum.USD: settings.CURRENCY_CODE_USD,
        AccountCurrencyEnum.EUR: settings.CURRENCY_CODE_EUR,
        AccountCurrencyEnum.GBP: settings.CURRENCY_CODE_GBP,
        AccountCurrencyEnum.JPY: settings.CURRENCY_CODE_JPY,
        AccountCurrencyEnum.TWD: settings.CURRENCY_CODE_TWD,
    }
    currency_code = currency_map.get(currency)
    if not currency_code:
        logger.error(f"Unsupported currency: {currency}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported currency: {currency}",
        )
    return currency_code


def split_into_digits(number: int | str) -> list[int]:
    return [int(digit) for digit in str(number)]


def calculate_luhn_check_digit(number: str) -> int:
    digits = split_into_digits(number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(split_into_digits(d * 2))
    return (10 - (total % 10)) % 10


def generate_account_number(currency: AccountCurrencyEnum) -> str:
    try:
        """
        full_account_number structure:
        [Bank Code (3 digits)][Branch Code (4 digits)][Currency Code (3 digits)][Random Digits (9+ digits)][Check Digit (1 digit)]
        Total Length: 20 digits
        """
        if not all([settings.BANK_CODE, settings.BANK_BRANCH_CODE]):
            logger.error("Bank code or branch code is not configured.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Bank configuration error. Please contact support.",
            )
        currency_code = get_currency_code(currency)
        prefix = f"{settings.BANK_CODE}{settings.BANK_BRANCH_CODE}{currency_code}"
        remaining_length = 20 - len(prefix) - 1
        random_number = "".join(
            secrets.choice("0123456789") for _ in range(remaining_length)
        )
        partial_account_number = f"{prefix}{random_number}"
        check_digit = calculate_luhn_check_digit(partial_account_number)
        full_account_number = f"{partial_account_number}{check_digit}"
        return full_account_number
    except HTTPException as http_exc:
        logger.error(
            f"Error generating account number: {http_exc.detail}", exc_info=True
        )
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error generating account number: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating account number. Please try again later.",
        )


EXHANGE_RATES = {
    "USD": {
        "EUR": Decimal("0.95"),
        "GBP": Decimal("0.79"),
        "JPY": Decimal("149.50"),
        "TWD": Decimal("32.30"),
    },
    "EUR": {
        "USD": Decimal("1.05"),
        "GBP": Decimal("0.83"),
        "JPY": Decimal("157.37"),
        "TWD": Decimal("33.99"),
    },
    "GBP": {
        "USD": Decimal("1.27"),
        "EUR": Decimal("1.20"),
        "JPY": Decimal("189.43"),
        "TWD": Decimal("40.90"),
    },
    "JPY": {
        "USD": Decimal("0.0067"),
        "EUR": Decimal("0.0064"),
        "GBP": Decimal("0.0053"),
        "TWD": Decimal("0.216"),
    },
    "TWD": {
        "USD": Decimal("0.031"),
        "EUR": Decimal("0.029"),
        "GBP": Decimal("0.024"),
        "JPY": Decimal("4.63"),
    },
}

CONVERSION_FEE_RATE = Decimal("0.005")


def get_exchange_rate(
    from_currency: AccountCurrencyEnum,
    to_currency: AccountCurrencyEnum,
) -> Decimal:
    if from_currency == to_currency:
        return Decimal("1.0")
    try:
        rate = EXHANGE_RATES[from_currency.value][to_currency.value]
        return rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except KeyError:
        logger.error(f"Exchange rate not found for {from_currency} to {to_currency}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exchange rate not found for {from_currency} to {to_currency}",
        )


def calculate_conversion(
    amount: Decimal,
    from_currency: AccountCurrencyEnum,
    to_currency: AccountCurrencyEnum,
) -> Tuple[Decimal, Decimal, Decimal]:
    if from_currency == to_currency:
        return amount, Decimal("1.0"), Decimal("0.00")

    exchange_rate = get_exchange_rate(from_currency, to_currency)

    conversion_fee = (amount * CONVERSION_FEE_RATE).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    amount_after_fee = amount - conversion_fee

    converted_amount = (amount_after_fee * exchange_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return converted_amount, exchange_rate, conversion_fee
