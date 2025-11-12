from fastapi_mail import ConnectionConfig, FastMail
from pydantic import SecretStr
from pathlib import Path
from backend.app.core.config import settings

TEMPLATE_DIR = Path(__file__).parent / "templates"

email_config = ConnectionConfig(
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_PORT=settings.SMTP_PORT,
    MAIL_SERVER=settings.SMTP_HOST,
    MAIL_USERNAME="",
    MAIL_PASSWORD=SecretStr(""),
    MAIL_SSL_TLS=False,
    MAIL_STARTTLS=False,
    USE_CREDENTIALS=False,
    VALIDATE_CERTS=False,
    TEMPLATE_FOLDER=TEMPLATE_DIR,
)

fast_mail = FastMail(email_config)