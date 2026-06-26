"""
user.py — Pydantic schemas for User API request/response shapes.

These are NOT the ORM models (those live in app/models/user.py).
ORM model = shape of data in the DATABASE.
Pydantic schema = shape of data in API REQUESTS and RESPONSES.

They look similar but are NOT the same — e.g., you never send a
hashed_password in an API response, and you never store a plain-text
password in the database.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    """Fields common to both create and read operations."""
    email: str


class UserCreate(UserBase):
    """Shape of data required to CREATE a user (request body)."""
    password: str  # Plain text — will be hashed before storing


class UserRead(UserBase):
    """Shape of data returned when READING a user (response body)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    github_username: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Notice: no hashed_password here — NEVER expose password hashes in API responses
