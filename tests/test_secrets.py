from app.services import secrets


def test_encrypt_round_trips():
    token = secrets.encrypt("s3cr3t-value")
    assert token != "s3cr3t-value"  # ciphertext, not plaintext
    assert secrets.decrypt(token) == "s3cr3t-value"


def test_encrypt_is_nondeterministic():
    # Fernet embeds a random IV, so the same plaintext yields different ciphertexts.
    assert secrets.encrypt("x") != secrets.encrypt("x")


def test_decrypt_handles_empty_and_garbage():
    assert secrets.decrypt("") == ""
    assert secrets.decrypt("not-a-valid-token") == ""


def test_round_trips_unicode():
    assert secrets.decrypt(secrets.encrypt("héllo→世界")) == "héllo→世界"
