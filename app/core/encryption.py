"""
encryption.py — Symmetric encryption for storing sensitive tokens.

Uses Fernet (AES-128-CBC with HMAC-SHA256) from the `cryptography` library.
We encrypt GitHub access tokens before storing them in the database so that
even if the DB is compromised, the tokens are useless without the key.

The ENCRYPTION_KEY must be a valid Fernet key (base64-encoded 32 bytes).
Generate one with:
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_fernet() -> Fernet:
    """Get the Fernet cipher initialized with the app's encryption key."""
    key = settings.ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt_token(plain_token: str) -> str:
    """Encrypt a plain-text token. Returns a base64-encoded string."""
    f = _get_fernet()
    return f.encrypt(plain_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted token. Raises InvalidToken if key is wrong or data is corrupted."""
    f = _get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()
