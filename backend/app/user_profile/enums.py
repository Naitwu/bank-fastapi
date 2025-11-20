from enum import Enum


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



class ImageTypeSchema(str, Enum):
    ID_PHOTO = "id_photo"
    PROFILE_PHOTO = "profile_photo"
    SIGNATURE_PHOTO = "signature_photo"
