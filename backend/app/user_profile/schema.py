from enum import Enum
from sqlmodel import Field, SQLModel
from datetime import date
from pydantic_extra_types.country import CountryShortName
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import field_validator
from backend.app.user_profile.utils import validate_id_dates
from backend.app.auth.schema import RoleCoiceSchema


class SalutationSchema(str, Enum):
    Mr = "Mr"
    Mrs = "Mrs"
    Miss = "Miss"


class GenderSchema(str, Enum):
    Male = "Male"
    Female = "Female"
    Other = "Other"


class MaritalStatusSchema(str, Enum):
    Single = "Single"
    Married = "Married"
    Divorced = "Divorced"
    Widowed = "Widowed"


class IdentificationTypeSchema(str, Enum):
    Passport = "Passport"
    NationalID = "NationalID"
    DriverLicense = "DriverLicense"


class EmploymentStatusSchema(str, Enum):
    Employed = "Employed"
    SelfEmployed = "SelfEmployed"
    Unemployed = "Unemployed"
    Student = "Student"
    Retired = "Retired"


class ProfileBaseSchema(SQLModel):
    title: SalutationSchema
    gender: GenderSchema
    date_of_birth: date
    country_of_birth: CountryShortName
    place_of_birth: str
    marital_status: MaritalStatusSchema
    means_of_identification: IdentificationTypeSchema
    id_issue_date: date
    id_expiry_date: date
    passport_number: str
    nationality: str
    Phone_number: PhoneNumber
    address: str
    city: str
    country: str
    employment_status: EmploymentStatusSchema
    employer_name: str
    employer_address: str
    employer_city: str
    employer_country: CountryShortName
    annual_income: float
    date_of_employment: date
    profile_photo_url: str | None = Field(default=None)
    id_photo_url: str | None = Field(default=None)
    signature_photo_url: str | None = Field(default=None)


class ProfileCreateSchema(ProfileBaseSchema):
    @field_validator("id_expiry_date")
    def check_id_dates(cls, v, values):
        issue_date = values.data.get("id_issue_date")
        if issue_date is not None:
            validate_id_dates(issue_date, v)
        return v


class ProfileUpdateSchema(ProfileBaseSchema):
    title: SalutationSchema | None = None
    gender: GenderSchema | None = None
    date_of_birth: date | None = None
    country_of_birth: CountryShortName | None = None
    place_of_birth: str | None = None
    marital_status: MaritalStatusSchema | None = None
    means_of_identification: IdentificationTypeSchema | None = None
    id_issue_date: date | None = None
    id_expiry_date: date | None = None
    passport_number: str | None = None
    nationality: str | None = None
    Phone_number: PhoneNumber | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    employment_status: EmploymentStatusSchema | None = None
    employer_name: str | None = None
    employer_address: str | None = None
    employer_city: str | None = None
    employer_country: CountryShortName | None = None
    annual_income: float | None = None
    date_of_employment: date | None = None

    @field_validator("id_expiry_date")
    def check_id_dates(cls, v: date | None, values) -> date | None:
        if v is not None:
            issue_date = values.data.get("id_issue_date")
            if issue_date is not None:
                validate_id_dates(issue_date, v)
        return v


class ImageTypeSchema(str, Enum):
    ID_PHOTO = "id_photo"
    PROFILE_PHOTO = "profile_photo"
    SIGNATURE_PHOTO = "signature_photo"

class ProfileResponseSchema(SQLModel):
    username: str
    first_name: str
    last_name: str
    email: str
    id_no: str
    role: RoleCoiceSchema
    profile: ProfileBaseSchema | None

    class Config:
        from_attributes = True

class PaginateddProfileResponseSchema(SQLModel):
    profiles: list[ProfileResponseSchema]
    total: int
    skip: int
    limit: int