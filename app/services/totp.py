"""RFC 6238 TOTP + backup codes — standard-library only (no pyotp dependency).

Used for optional, opt-in two-factor auth on admin login. The panel and the
`/api/v1` token login both call :func:`verify` (via the auth service) only when a
user has 2FA enabled, so accounts without it are entirely unaffected.

Interoperable with Google Authenticator / 1Password / Authy: HMAC-SHA1, 6 digits,
30-second period, which is the de-facto default those apps assume from an
``otpauth://`` URI.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

DIGITS = 6
PERIOD = 30
_SECRET_BYTES = 20  # 160 bits — the RFC-recommended SHA-1 key length.
_BACKUP_CODE_COUNT = 10


def generate_secret() -> str:
    """Return a fresh base32 TOTP secret (unpadded, uppercase)."""
    raw = secrets.token_bytes(_SECRET_BYTES)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _b32decode(secret: str) -> bytes:
    padded = secret.strip().replace(" ", "").upper()
    padded += "=" * (-len(padded) % 8)
    return base64.b32decode(padded, casefold=True)


def _hotp(secret: str, counter: int) -> str:
    key = _b32decode(secret)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**DIGITS)
    return str(code).zfill(DIGITS)


def _normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "") if ch.isdigit())


def verify(secret: str, code: str, *, window: int = 1, at: float | None = None) -> bool:
    """True if ``code`` is a valid TOTP for ``secret`` within ±``window`` steps.

    The ±1-step window tolerates clock skew between server and authenticator app
    (the standard tolerance). Comparison is constant-time.
    """
    normalized = _normalize_code(code)
    if len(normalized) != DIGITS:
        return False
    counter = int((time.time() if at is None else at) // PERIOD)
    for drift in range(-window, window + 1):
        candidate = _hotp(secret, counter + drift)
        if hmac.compare_digest(candidate, normalized):
            return True
    return False


def provisioning_uri(secret: str, account_name: str, *, issuer: str = "Tetra AI Cloud") -> str:
    """Build the ``otpauth://`` URI an authenticator app scans/imports."""
    label = quote(f"{issuer}:{account_name}", safe=":")
    params = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": str(DIGITS),
            "period": str(PERIOD),
        }
    )
    return f"otpauth://totp/{label}?{params}"


# --- Recovery / backup codes ------------------------------------------------
#
# One-time codes a user can spend when they lose their authenticator. Stored as
# sha256 hashes (they're high-entropy, so a plain fast hash is sufficient) and
# consumed on use.


def generate_backup_codes(count: int = _BACKUP_CODE_COUNT) -> list[str]:
    """Return ``count`` human-friendly one-time recovery codes (shown once)."""
    return [f"{secrets.randbelow(10**5):05d}-{secrets.randbelow(10**5):05d}" for _ in range(count)]


def hash_backup_code(code: str) -> str:
    normalized = code.strip().replace(" ", "").lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
