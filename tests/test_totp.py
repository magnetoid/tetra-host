"""RFC 6238 TOTP core (app/services/totp.py) — pure, no DB/app."""

import base64
import struct

from app.services import totp


def _at(secret: str, t: float) -> str:
    """Compute the expected 6-digit code the same way an authenticator would."""
    counter = int(t // totp.PERIOD)
    return totp._hotp(secret, counter)


def test_secret_is_valid_base32_and_random():
    a = totp.generate_secret()
    b = totp.generate_secret()
    assert a != b
    # Decodes as base32 (padding re-added internally).
    decoded = totp._b32decode(a)
    assert len(decoded) == totp._SECRET_BYTES


def test_rfc6238_known_vector():
    # RFC 6238 test vector: SHA-1, seed "12345678901234567890", T=59 -> 94287082.
    seed = b"12345678901234567890"
    secret = base64.b32encode(seed).decode()
    counter = 59 // totp.PERIOD
    digest = totp._hotp(secret, counter)
    assert digest == "287082"  # last 6 digits of the RFC's 8-digit 94287082


def test_verify_accepts_current_and_drift():
    secret = totp.generate_secret()
    now = 1_000_000.0
    assert totp.verify(secret, _at(secret, now), at=now)
    # ±1 step tolerated (clock skew).
    assert totp.verify(secret, _at(secret, now - totp.PERIOD), at=now)
    assert totp.verify(secret, _at(secret, now + totp.PERIOD), at=now)


def test_verify_rejects_out_of_window_and_garbage():
    secret = totp.generate_secret()
    now = 1_000_000.0
    assert not totp.verify(secret, _at(secret, now - 3 * totp.PERIOD), at=now)
    assert not totp.verify(secret, "000000", at=now) or _at(secret, now) == "000000"
    assert not totp.verify(secret, "12", at=now)  # too short
    assert not totp.verify(secret, "", at=now)
    assert not totp.verify(secret, "abcdef", at=now)


def test_verify_tolerates_spaces_and_nondigits():
    secret = totp.generate_secret()
    now = 1_000_000.0
    code = _at(secret, now)
    spaced = f"{code[:3]} {code[3:]}"
    assert totp.verify(secret, spaced, at=now)


def test_provisioning_uri_shape():
    uri = totp.provisioning_uri("ABC234", "admin@example.com", issuer="Tetra AI Cloud")
    assert uri.startswith("otpauth://totp/Tetra%20AI%20Cloud:admin%40example.com?")
    assert "issuer=Tetra+AI+Cloud" in uri
    assert "secret=ABC234" in uri
    assert "algorithm=SHA1" in uri
    assert "digits=6" in uri
    assert "period=30" in uri


def test_backup_codes_are_unique_and_hash_stably():
    codes = totp.generate_backup_codes(10)
    assert len(codes) == 10
    assert len(set(codes)) == 10
    # Hash is stable and normalization-insensitive to spacing/case.
    h = totp.hash_backup_code(codes[0])
    assert totp.hash_backup_code(codes[0]) == h
    assert totp.hash_backup_code(codes[0].upper()) == h
    assert totp.hash_backup_code(f" {codes[0]} ") == h
    assert totp.hash_backup_code(codes[1]) != h


def test_hotp_matches_manual_computation():
    # Sanity: our _hotp matches a hand-rolled dynamic-truncation for a fixed key.
    secret = totp.generate_secret()
    key = totp._b32decode(secret)
    import hashlib
    import hmac

    counter = 42
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    expected = str((struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 10**6).zfill(6)
    assert totp._hotp(secret, counter) == expected
