"""
security.py — Password hashing and JWT token utilities.

This is the crypto layer of the auth system. It handles:
  1. Password hashing (bcrypt via passlib)
  2. JWT creation and decoding (HS256 via python-jose)

Kept separate from business logic (auth_service.py) because:
  - These are pure functions (no DB, no Redis)
  - Easy to unit test in isolation
  - Reusable across different parts of the app
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ── Password hashing ─────────────────────────────────────────────────────────
# CryptContext handles the bcrypt algorithm selection and auto-upgrades.
# "deprecated=auto" means if you later switch to argon2, old bcrypt
# hashes still verify correctly but new passwords use the new algorithm.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT tokens ───────────────────────────────────────────────────────────────
ALGORITHM = "HS256"


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a short-lived JWT access token.

    The `sub` (subject) claim should be the user's ID as a string.
    The `exp` (expiration) claim is set automatically.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """
    Create a long-lived JWT refresh token.

    Refresh tokens live longer (days vs minutes) and are stored in Redis
    so they can be revoked. When the access token expires, the client
    sends the refresh token to get a new access token without re-entering
    their password.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token. Raises JWTError on invalid/expired tokens.

    Returns the payload dict (contains 'sub', 'exp', 'type').
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
