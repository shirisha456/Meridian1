import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.encryption import EncryptionNotConfigured, decrypt, encrypt


def _settings_with_key() -> Settings:
    return Settings(encryption_key=Fernet.generate_key().decode())


def test_encrypt_round_trips():
    settings = _settings_with_key()
    ciphertext = encrypt("plaid-access-token-value", settings)
    assert decrypt(ciphertext, settings) == "plaid-access-token-value"


def test_ciphertext_is_never_the_plaintext():
    settings = _settings_with_key()
    ciphertext = encrypt("plaid-access-token-value", settings)
    assert b"plaid-access-token-value" not in ciphertext


def test_raises_when_encryption_key_not_configured():
    settings = Settings(encryption_key="")
    with pytest.raises(EncryptionNotConfigured):
        encrypt("anything", settings)


def test_decrypt_fails_with_a_different_key():
    settings_a = _settings_with_key()
    settings_b = _settings_with_key()
    ciphertext = encrypt("secret", settings_a)
    with pytest.raises(InvalidToken):
        decrypt(ciphertext, settings_b)
