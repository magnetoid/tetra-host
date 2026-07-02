"""Symmetric encryption at rest for tenant secrets (env vars).

A single Fernet box keyed off ``APP_SECRET`` (SHA-256 → 32-byte urlsafe key). Values
are encrypted before they touch the database and decrypted only at injection time.
Rotating ``APP_SECRET`` invalidates stored ciphertexts (they decrypt to "" and must be
re-entered) — a dedicated ``ENCRYPTION_KEY`` can be introduced later without changing callers.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


@lru_cache(maxsize=1)
def _box() -> Fernet:
    secret = get_settings().app_secret.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    """Encrypt a plaintext string to a urlsafe ciphertext token."""
    return _box().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a ciphertext token; return "" if it is empty or undecryptable."""
    if not token:
        return ""
    try:
        return _box().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
