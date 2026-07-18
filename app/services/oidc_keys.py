"""OIDC signing key: RS256 JWT signing + JWKS export on top of `cryptography`.

Tetra only ever SIGNS id_tokens (Mailcow verifies them against our JWKS), so this
module implements signing + public-key publication only — no verification, no new
dependency beyond `cryptography` (already required). The private key is supplied
as PEM via config (`oidc_private_key_pem`); generate one with scripts/gen-oidc-key.sh.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _int_to_b64url(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return _b64url(value.to_bytes(length, "big"))


class OIDCSigningKey:
    """Wraps an RSA private key for RS256 JWT signing + JWKS publication."""

    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        self._private_key = private_key
        self._public_key = private_key.public_key()
        # Stable key id: truncated SHA-256 of the DER SubjectPublicKeyInfo. Rotating
        # the key changes the PEM → changes the kid, so old + new keys are distinct.
        der = self._public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.kid = _b64url(hashlib.sha256(der).digest())[:16]

    @classmethod
    def from_pem(cls, pem: str) -> "OIDCSigningKey":
        # Tolerate a single-line env value where newlines are written as literal
        # "\n" (common in .env / systemd EnvironmentFile) — real PEMs are unaffected.
        normalized = pem.replace("\\n", "\n").strip()
        key = serialization.load_pem_private_key(normalized.encode("utf-8"), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise ValueError("OIDC signing key must be an RSA private key.")
        if key.key_size < 2048:
            raise ValueError("OIDC signing key must be at least 2048 bits.")
        return cls(key)

    def sign_jwt(self, claims: dict[str, Any]) -> str:
        header = {"alg": "RS256", "typ": "JWT", "kid": self.kid}
        segments = [
            _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url(json.dumps(claims, separators=(",", ":")).encode("utf-8")),
        ]
        signing_input = ".".join(segments).encode("ascii")
        signature = self._private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        segments.append(_b64url(signature))
        return ".".join(segments)

    def public_jwk(self) -> dict[str, str]:
        numbers = self._public_key.public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.kid,
            "n": _int_to_b64url(numbers.n),
            "e": _int_to_b64url(numbers.e),
        }

    def jwks(self) -> dict[str, list[dict[str, str]]]:
        return {"keys": [self.public_jwk()]}


@lru_cache
def _cached_key(pem: str) -> OIDCSigningKey:
    return OIDCSigningKey.from_pem(pem)


def load_signing_key(pem: str) -> OIDCSigningKey:
    """Load (and cache) the signing key from PEM. Cached by PEM content so a
    rotated key is picked up automatically."""
    return _cached_key(pem)


def now_ts() -> int:
    return int(time.time())
