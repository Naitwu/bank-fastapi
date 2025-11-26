from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field
from backend.app.bank_account.enums import AccountTypeEnum, AccountStatusEnum, AccountCurrencyEnum

class BankAccountBaseSchema(SQLModel):
    account_type: AccountTypeEnum
    account_status: AccountStatusEnum = Field(nullable=False, default=AccountStatusEnum.Pending)
    currency: AccountCurrencyEnum
    account_number: str | None = Field(default=None, unique=True, index=True)
    account_name: str
    balance: float = Field(default=0.0)
    is_primary: bool = Field(default=False)
    kyc_submitted: bool = Field(default=False)
    kyc_verified: bool = Field(default=False)
    kyc_verified_by: UUID | None = Field(default=None)
    interest_rate: float = Field(default=0.0)

class BankAccountCreateSchema(BankAccountBaseSchema):
    account_number: str | None = None

class BankAccountReadSchema(BankAccountBaseSchema):
    id: UUID
    user_id: UUID
    account_number: str | None = None
    created_at: datetime
    updated_at: datetime

class BankAccountUpdateSchema(BankAccountBaseSchema):
    account_number: str | None = None
    is_primary: bool | None = None
    account_status: AccountStatusEnum | None = None