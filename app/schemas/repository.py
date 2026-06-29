"""
repository.py — Pydantic schemas for Repository API shapes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RepositoryCreate(BaseModel):
    """Shape of data to register a repo in PRScope."""
    github_id: int
    full_name: str
    default_branch: str = "main"


class RepositoryRead(BaseModel):
    """Shape of data returned when reading a repository."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    github_id: int
    full_name: str
    default_branch: str
    is_active: bool
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
