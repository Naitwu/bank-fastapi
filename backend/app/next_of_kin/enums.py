from enum import Enum


class RelationshipTypeEnum(str, Enum):
    Parent = "Parent"
    Sibling = "Sibling"
    Spouse = "Spouse"
    Child = "Child"
    Other = "Other"

