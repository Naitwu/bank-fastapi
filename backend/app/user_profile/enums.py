from enum import Enum


class SalutationEnum(str, Enum):
    Mr = "Mr"
    Mrs = "Mrs"
    Miss = "Miss"


class GenderEnum(str, Enum):
    Male = "Male"
    Female = "Female"
    Other = "Other"


class MaritalStatusEnum(str, Enum):
    Single = "Single"
    Married = "Married"
    Divorced = "Divorced"
    Widowed = "Widowed"


class IdentificationTypeEnum(str, Enum):
    Passport = "Passport"
    NationalID = "NationalID"
    DriverLicense = "DriverLicense"


class EmploymentStatusEnum(str, Enum):
    Employed = "Employed"
    SelfEmployed = "SelfEmployed"
    Unemployed = "Unemployed"
    Student = "Student"
    Retired = "Retired"



class ImageTypeEnum(str, Enum):
    ID_PHOTO = "id_photo"
    PROFILE_PHOTO = "profile_photo"
    SIGNATURE_PHOTO = "signature_photo"
