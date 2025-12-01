import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql as pg
from sqlmodel import Column, Field, Relationship
from backend.app.transaction.schema import TransactionBaseSchema
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from backend.app.auth.models import User
    from backend.app.bank_account.models import BankAccount

class Transaction(TransactionBaseSchema, table=True):
    id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
        ),
        default_factory=uuid.uuid4,
    )
    sender_account_id: uuid.UUID | None = Field(
        foreign_key="bankaccount.id",
        default=None,
    )
    receiver_account_id: uuid.UUID | None = Field(
        foreign_key="bankaccount.id",
        default=None,
    )

    sender_id: uuid.UUID | None = Field(
        foreign_key="user.id",
        default=None,
    )
    receiver_id: uuid.UUID | None = Field(
        foreign_key="user.id",
        default=None,
    )
    processed_by_id: uuid.UUID | None = Field(
        foreign_key="user.id",
        default=None,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=True,
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
    transaction_metadata: dict | None = Field(sa_column=Column(JSONB), default=None)

    sender_account: "BankAccount" = Relationship(
        back_populates="sent_transactions" ,sa_relationship_kwargs={"foreign_keys": "Transaction.sender_account_id"}
    )
    receiver_account: "BankAccount" = Relationship(
        back_populates="received_transactions", sa_relationship_kwargs={"foreign_keys": "Transaction.receiver_account_id"}
    )
    sender: "User" = Relationship(
        back_populates="sent_transactions", sa_relationship_kwargs={"foreign_keys": "Transaction.sender_id"}
    )
    receiver: "User" = Relationship(
        back_populates="received_transactions", sa_relationship_kwargs={"foreign_keys": "Transaction.receiver_id"}
    )
    processed_by: "User" = Relationship(
        back_populates="processed_transactions", sa_relationship_kwargs={"foreign_keys": "Transaction.processed_by_id"}
    )