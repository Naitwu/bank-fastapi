import uuid
from decimal import Decimal
from datetime import datetime
from typing_extensions import Annotated
from sqlmodel import SQLModel, Field, Column
from backend.app.transaction.enums import TransactionTypeEnum, TransactionStatusEnum, TransactionCategoryEnum
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB

class TransactionBaseSchema(SQLModel):
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    description: str = Field(max_length=255)
    reference: str = Field(unique=True, index=True)
    transaction_type: TransactionTypeEnum
    transaction_category: TransactionCategoryEnum
    status: TransactionStatusEnum = Field(default=TransactionStatusEnum.Pending)
    balance_before: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    balance_after: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    transaction_metadata: dict | None = Field(sa_column=Column(JSONB), default=None)
    failed_reason: str | None = Field(default=None)

class TransactionCreateSchema(TransactionBaseSchema):
    pass

class TransactionReadSchema(TransactionBaseSchema):
    id: uuid.UUID
    created_at: datetime = Field(
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
        )
    )
    completed_at: datetime | None = Field(
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        default=None,
    )

class TransactionUpdateSchema(TransactionBaseSchema):
    pass

class DepositRequestSchema(SQLModel):
    account_id: uuid.UUID
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    description: str = Field(max_length=255)