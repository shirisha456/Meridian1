from uuid import uuid4

import jwt
import pytest

from app.auth.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.config import Settings


def test_hash_password_is_not_the_plaintext():
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert hashed.startswith("$argon2id$")


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery")
    assert verify_password("correct horse battery", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery")
    assert verify_password("wrong password", hashed) is False


def test_generate_refresh_token_is_high_entropy_and_unique():
    tokens = {generate_refresh_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 48 for t in tokens)


def test_hash_refresh_token_is_deterministic_and_not_reversible_looking():
    raw = generate_refresh_token()
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert hash_refresh_token(raw) != raw


_TEST_SECRET_A = "test-only-secret-key-padded-to-32-bytes-minimum"
_TEST_SECRET_B = "a-completely-different-test-secret-also-32-bytes-plus"


def test_access_token_round_trips_and_carries_expected_claims():
    settings = Settings(jwt_secret=_TEST_SECRET_A, environment="test")
    user_id = uuid4()

    token = create_access_token(user_id, settings)
    payload = decode_access_token(token, settings)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "exp" in payload


def test_access_token_rejects_wrong_secret():
    settings = Settings(jwt_secret=_TEST_SECRET_A, environment="test")
    other_settings = Settings(jwt_secret=_TEST_SECRET_B, environment="test")
    token = create_access_token(uuid4(), settings)

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, other_settings)
