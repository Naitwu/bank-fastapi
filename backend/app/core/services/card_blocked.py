from datetime import datetime
from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate
from backend.app.core.services.card_activated import CardActivatedEmail

class CardBlockedEmail(EmailTemplate):
    template_name = "card_blocked.html"
    template_name_plain = "card_blocked.txt"
    subject = "Your Virtual Card Has Been Blocked"

async def send_card_blocked_email(
    email: str,
    full_name: str,
    card_type: str,
    masked_card_number: str,
    block_reason: str,
    block_reason_description: str,
    blocked_at: datetime,
) -> None:
    context = {
        "full_name": full_name,
        "card_type": card_type,
        "masked_card_number": masked_card_number,
        "block_reason": block_reason,
        "block_reason_description": block_reason_description,
        "blocked_at": blocked_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "site_name": settings.SITE_NAME,
        "support_email": settings.SUPPORT_EMAIL,
    }

    await CardBlockedEmail.send_email(email_to=email, context=context)