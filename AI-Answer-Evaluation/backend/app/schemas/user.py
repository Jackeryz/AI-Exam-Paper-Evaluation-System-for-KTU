"""Pydantic schemas for Authentication and Users."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    department: Optional[str] = "KTU Engineering"


class UserCreate(UserBase):
    password: str
    role: Optional[UserRole] = UserRole.TEACHER


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    user_id: int
    full_name: str


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
