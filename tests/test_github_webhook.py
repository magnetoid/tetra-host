from app.services.github_webhook import (
    branch_from_ref,
    push_ref,
    sign,
    verify_signature,
)

_SECRET = "whsec-abc123"
_BODY = b'{"ref":"refs/heads/main"}'


def test_verify_accepts_a_correct_signature():
    header = sign(_SECRET, _BODY)
    assert header.startswith("sha256=")
    assert verify_signature(_SECRET, _BODY, header) is True


def test_verify_rejects_wrong_secret_body_and_missing_header():
    header = sign(_SECRET, _BODY)
    assert verify_signature("other-secret", _BODY, header) is False
    assert verify_signature(_SECRET, b"tampered", header) is False
    assert verify_signature(_SECRET, _BODY, None) is False
    assert verify_signature(_SECRET, _BODY, "sha1=deadbeef") is False
    assert verify_signature("", _BODY, header) is False


def test_push_ref_and_branch_extraction():
    assert push_ref({"ref": "refs/heads/main"}) == "refs/heads/main"
    assert push_ref({}) == ""
    assert branch_from_ref("refs/heads/feature/x") == "feature/x"
    assert branch_from_ref("refs/tags/v1") == ""
