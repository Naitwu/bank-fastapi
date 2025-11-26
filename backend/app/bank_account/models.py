import uuid
from datetime import datetime, timezone
from sqlmodel import Field, Column, Relationship
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy import text, func
from backend.app.bank_account.schema import BankAccountBaseSchema
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.auth.models import User

class BankAccount(BankAccountBaseSchema, table=True):
    id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
        ),
        default_factory=uuid.uuid4,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            onupdate=func.current_timestamp(),
            nullable=False,
        ),
    )
    kyc_verified_on: datetime | None = Field(
        default=None,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
        ),
    )
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    user: "User" = Relationship(back_populates="bank_accounts")