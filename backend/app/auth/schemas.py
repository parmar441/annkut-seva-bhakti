import re

from pydantic import BaseModel, Field, field_validator

from ..enums import SECURITY_ANSWER_MIN_LENGTH, SECURITY_QUESTIONS, MandalName, MandalType
from .passwords import normalize_answer

USERNAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$"


def validate_question(question: str) -> str:
    if question not in SECURITY_QUESTIONS:
        raise ValueError("Choose one of the listed questions.")
    return question


def validate_answer(answer: str) -> str:
    if len(normalize_answer(answer)) < SECURITY_ANSWER_MIN_LENGTH:
        raise ValueError(f"Use at least {SECURITY_ANSWER_MIN_LENGTH} letters or numbers.")
    return answer


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)
    mandal_name: MandalName
    mandal_type: MandalType
    security_question: str
    security_answer: str = Field(min_length=1, max_length=200)

    @field_validator("security_question")
    @classmethod
    def _question(cls, v: str) -> str:
        return validate_question(v)

    @field_validator("security_answer")
    @classmethod
    def _answer(cls, v: str) -> str:
        return validate_answer(v)

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
