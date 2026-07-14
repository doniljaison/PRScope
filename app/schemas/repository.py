"""
repository.py — Pydantic schemas for Repository API shapes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RepositoryCreate(BaseModel):
    """Shape of data to register a repo in PRScope."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "github_id": 123456789,
                "full_name": "octocat/Hello-World",
                "default_branch": "main",
            }
        },
    )

    github_id: int
    full_name: str
    default_branch: str = "main"


class RepositoryRead(BaseModel):
    """Shape of data returned when reading a repository."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "github_id": 123456789,
                "full_name": "octocat/Hello-World",
                "default_branch": "main",
                "is_active": True,
                "owner_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "created_at": "2026-07-01T10:00:00Z",
                "updated_at": "2026-07-14T15:30:00Z",
            }
        },
    )

    id: uuid.UUID
    github_id: int
    full_name: str
    default_branch: str
    is_active: bool
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
