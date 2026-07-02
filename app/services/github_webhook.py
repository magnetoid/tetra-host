"""GitHub webhook helpers — HMAC signature verification + push-event parsing.

Kept pure (no I/O) so the security-critical signature check is trivially unit-testable.
"""

import hashlib
import hmac

_SHA256_PREFIX = "sha256="
_BRANCH_PREFIX = "refs/heads/"


def sign(secret: str, body: bytes) -> str:
    """Compute the ``sha256=<hex>`` signature GitHub would send for ``body``."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{_SHA256_PREFIX}{digest}"


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Constant-time verify a GitHub ``X-Hub-Signature-256`` header against ``body``."""
    if not secret or not signature_header or not signature_header.startswith(_SHA256_PREFIX):
        return False
    return hmac.compare_digest(sign(secret, body), signature_header)


def push_ref(payload: dict) -> str:
    """The pushed ref, e.g. ``refs/heads/main`` ("" if absent)."""
    ref = payload.get("ref")
    return ref if isinstance(ref, str) else ""


def branch_from_ref(ref: str) -> str:
    """``refs/heads/main`` → ``main``; "" for tags or malformed refs."""
    return ref[len(_BRANCH_PREFIX):] if ref.startswith(_BRANCH_PREFIX) else ""
