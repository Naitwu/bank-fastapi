import uuid
from decimal import Decimal
from datetime import datetime
from typing_extensions import Annotated
from fastapi import Query
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

class TransferRequestSchema(SQLModel):
    sender_account_id: uuid.UUID
    receiver_account_number: str = Field(max_length=20)
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    description: str = Field(max_length=255)
    security_answer: str = Field(max_length=255)

class TransferOTPVerificationSchema(SQLModel):
    transfer_reference: str
    otp: str = Field(max_length=6, min_length=6)

class TransferResponseSchema(SQLModel):
    status: str
    message: str
    data: dict | None = None

class CurrencyConversionSchema(SQLModel):
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    from_currency: str
    to_currency: str
    exchange_rate: Decimal
    original_amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    converted_amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    conversion_fee: Decimal=Field(default=Decimal("0.00"))

class WithdrawalRequestSchema(SQLModel):
    account_number: str = Field(max_length=20)
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    username: str = Field(max_length=12, min_length=1)
    description: str = Field(max_length=255)

class TransactionHistoryResponseSchema(SQLModel):
    id: uuid.UUID
    reference: str
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    description: str
    transaction_type: TransactionTypeEnum
    transaction_category: TransactionCategoryEnum
    transaction_status: TransactionStatusEnum
    created_at: datetime
    completed_at: datetime | None = None
    balance_after: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    currency: str | None = None
    converted_amount: str | None = None
    from_currency: str | None = None
    to_currency: str | None = None
    counterparty_account: str | None = None
    counterparty_name: str | None = None

class PaginatedTransactionHistoryResponseSchema(SQLModel):
    total: int
    skip: int
    limit: int
    transactions: list[TransactionHistoryResponseSchema]

class TransactionFilterParamsSchema(SQLModel):
    start_date: datetime | None = Query(
        default=None,
        description="Filter transactions from this date (inclusive). Format: YYYY-MM-DDTHH:MM:SSZ",
        example="2025-01-01T00:00:00Z"
    )
    end_date: datetime | None = Query(
        default=None,
        description="Filter transactions up to this date (inclusive). Format: YYYY-MM-DDTHH:MM:SSZ",
        example="2025-12-31T23:59:59Z"
    )
    transaction_type: TransactionTypeEnum | None = Query(
        default=None,
        description="Filter by transaction type (e.g., Deposit, Withdrawal, Transfer)."
    )
    transaction_category: TransactionCategoryEnum | None = Query(
        default=None,
        description="Filter by transaction category (e.g., Credit, Debit)."
    )
    transaction_status: TransactionStatusEnum | None = Query(
        default=None,
        description="Filter by transaction status (e.g., Pending, Completed, Failed)."
    )
    min_amount: Decimal | None = Query(
        default=None,
        ge=0,
        description="Filter transactions with amount greater than or equal to this value."
    )
    max_amount: Decimal | None = Query(
        default=None,
        ge=0,
        description="Filter transactions with amount less than or equal to this value."
    )

class StatementRequestSchema(SQLModel):
    start_date: datetime
    end_date: datetime
    account_number: str | None = Field(
        default=None,
        max_length=20,
        description="Optional account number to filter the statement for a specific bank account."
    )

class StatementResponseSchema(SQLModel):
    status: str
    message: str
    task_id: str | None = None
    statement_id : str | None = None
    generated_at: datetime | None = None
    expires_at: datetime | None = None

class TransactionReviewSchema(SQLModel):
    if_fraud: bool
    notes: str | None = None
    approve_transaction: bool = False