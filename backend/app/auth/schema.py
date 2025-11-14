import uuid
from sqlmodel import SQLModel, Field
from pydantic import EmailStr, field_validator
from fastapi import HTTPException, status
from enum import Enum

class SecurityQuestionsSchema(str, Enum):
    FIRST_PET = "first_pet"
    BIRTH_CITY = "birth_city"
    ELEMENTARY_SCHOOL = "elementary_school"
    FAVORITE_BOOK = "favorite_book"
    CHILDHOOD_FRIEND = "childhood_friend"
    FAVORITE_FOOD = "favorite_food"

    @classmethod
    def get_description(cls, value: "SecurityQuestionsSchema") -> str:
        descriptions = {
            cls.FIRST_PET: "你的第一隻寵物叫什麼名字？",
            cls.BIRTH_CITY: "你出生的城市是哪裡？",
            cls.ELEMENTARY_SCHOOL: "你的小學校名是什麼？",
            cls.FAVORITE_BOOK: "你最喜歡的書是什麼？",
            cls.CHILDHOOD_FRIEND: "你童年時期最好的朋友叫什麼名字？",
            cls.FAVORITE_FOOD: "你最喜歡的食物是什麼？",
        }
        return descriptions.get(value, "Unknown security question")

class AccountStatusSchema(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    PENDING = "pending"

class RoleCoiceSchema(str, Enum):
    CUSTOMER = "customer"
    TELLER = "teller"
    ACCOUNT_EXECUTIVE = "account_executive"
    BRANCH_MANAGER = "branch_manager"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class BaseUserSchema(SQLModel):
    username: str | None = Field(default=None, max_length=30, unique=True)
    email: EmailStr =  Field(index=True, unique=True, max_length=255)
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    id_no: int = Field(unique=True, gt=0)
    is_active: bool = False
    is_superuser: bool = False
    security_question: SecurityQuestionsSchema = Field(max_length=50)
    security_answer: str = Field(max_length=50)
    account_status: AccountStatusSchema = Field(default=AccountStatusSchema.INACTIVE)
    role: RoleCoiceSchema = Field(default=RoleCoiceSchema.CUSTOMER)

class UserCreateSchema(BaseUserSchema):
    password: str = Field(min_length=8, max_length=40)
    confirm_password: str = Field(min_length=8, max_length=40)

    @field_validator("confirm_password")
    def validate_confirm_password(cls, v, values):
        if "password" in values.data and v != values.data["password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Password and confirm password do not match.",
                    "action": "Please ensure both passwords are identical."
                }
            )
        return v

class UserReadSchema(BaseUserSchema):
    id: uuid.UUID
    full_name: str

class EmailRequestSchema(SQLModel):
    email: EmailStr

class LoginRequestSchema(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=40)

class OTPVerifyRequestSchema(SQLModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)

class PasswordResetRequestSchema(SQLModel):
    email: EmailStr

class PasswordResetConfirmSchema(SQLModel):
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=40,
    )
    confirm_password: str = Field(
        ...,
        min_length=8,
        max_length=40,
    )
    @field_validator("confirm_password")
    def validate_confirm_password(cls, v, values):
        if "new_password" in values.data and v != values.data["new_password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "New password and confirm password do not match.",
                    "action": "Please ensure both passwords are identical."
                }
            )
        return v