from cryptography.fernet import Fernet

from app.core.config import Settings, get_settings
from app.errors import ServiceUnavailableError


class EncryptionNotConfigured(ServiceUnavailableError):
    error_type = "encryption_not_configured"


def _get_fernet(settings: Settings | None = None) -> Fernet:
    settings = settings or get_settings()
    if not settings.encryption_key:
        raise EncryptionNotConfigured(
            "ENCRYPTION_KEY is not set; cannot encrypt or decrypt provider "
            'credentials. Generate one with: python -c "from cryptography.fernet '
            'import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str, settings: Settings | None = None) -> bytes:
    return _get_fernet(settings).encrypt(plaintext.encode())


def decrypt(ciphertext: bytes, settings: Settings | None = None) -> str:
    return _get_fernet(settings).decrypt(ciphertext).decode()
