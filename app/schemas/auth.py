"""
auth.py — Pydantic schemas for authentication endpoints.
"""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Shape of the login request body."""
    email: str
    password: str


class RefreshRequest(BaseModel):
    """Shape of the refresh token request body."""
    refresh_token: str


class TokenResponse(BaseModel):
    """Shape of the token response (login, register, refresh)."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
