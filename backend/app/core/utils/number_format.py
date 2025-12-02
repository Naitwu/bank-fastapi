from decimal import Decimal
from typing import Union

def format_decimal(amount: Union[Decimal, float, int, str]) -> str:
    try:
        decimal_amount = Decimal(str(amount))
        return f"{decimal_amount:,.2f}"
    except (ValueError, TypeError, AttributeError) as e:
        return str(amount)

def parse_decimal(amount: Union[float, int, str]) -> Decimal:
    try:
        if isinstance(amount, str):
            amount = amount.replace(",", "")
        return Decimal(amount)
    except (ValueError, TypeError, AttributeError) as e:
        raise ValueError(f"Invalid amount format: {amount}") from e