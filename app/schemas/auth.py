"""
auth.py — Pydantic schemas for authentication endpoints.
"""

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    """Shape of the login request body."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "developer@company.com", "password": "secureP@ss123"}
        },
    )

    email: str
    password: str


class RefreshRequest(BaseModel):
    """Shape of the refresh token request body."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"refresh_token": "eyJhbGciOiJIUzI1NiIs..."}
        },
    )

    refresh_token: str


class TokenResponse(BaseModel):
    """Shape of the token response (login, register, refresh)."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
            }
        },
    )

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic message response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"message": "Successfully logged out"}
        },
    )

    message: str
