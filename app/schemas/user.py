"""Pydantic schemas for User API shapes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "developer@company.com", "password": "secureP@ss123"}
        },
    )
    password: str


class UserRead(UserBase):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "email": "developer@company.com",
                "github_username": "octocat",
                "github_id": 583231,
                "is_active": True,
                "created_at": "2026-07-01T10:00:00Z",
                "updated_at": "2026-07-14T15:30:00Z",
            }
        },
    )
    id: uuid.UUID
    github_username: str | None
    github_id: int | None = None
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
