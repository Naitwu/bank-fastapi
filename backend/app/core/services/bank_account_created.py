from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate

class BankAccountCreatedEmail(EmailTemplate):
    template_name = "bank_account_created.html"
    template_name_plain = "bank_account_created.txt"
    subject = f"Your new bank account has been created on {settings.SITE_NAME}"

async def send_bank_account_created_email(
    email: str,
    full_name: str,
    account_number: str,
    account_name: str,
    account_type: str,
    currency: str,
) -> None:
    context = {
        "full_name": full_name,
        "account_number": account_number,
        "account_name": account_name,
        "account_type": account_type,
        "currency": currency,
        "site_name": settings.SITE_NAME,
        "support_email": settings.SUPPORT_EMAIL,
    }
    await BankAccountCreatedEmail.send_email(email_to=email, context=context)
