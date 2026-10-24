import re

from pydantic import BaseModel, Field, field_validator

from ..enums import MandalName, MandalType

USERNAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$"


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)
    mandal_name: MandalName
    mandal_type: MandalType

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Enter your full name.")
        return v

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip()
        if not re.match(USERNAME_PATTERN, v):
            raise ValueError("Use 3–32 letters, numbers, dots, dashes or underscores.")
        return v


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
