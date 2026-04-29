"""Encryption helpers for user-provided API keys."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from doormat.config import settings

_FERNET_PREFIX = "fernet:"


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt a secret before storing it locally."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return _FERNET_PREFIX + _fernet().encrypt(cleaned.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt a stored secret, accepting legacy plaintext values during migration."""
    if not value:
        return None
    if not value.startswith(_FERNET_PREFIX):
        if not settings.SECRET_KEY:
            raise ValueError("SECRET_KEY must be configured before reading legacy API keys")
        return value
    token = value.removeprefix(_FERNET_PREFIX).encode("ascii")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored secret could not be decrypted") from exc


def secret_last4(value: str | None) -> str | None:
    """Return a masked hint for an encrypted or legacy plaintext secret."""
    try:
        secret = decrypt_secret(value)
    except ValueError:
        return None
    return secret[-4:] if secret else None


def has_secret(value: str | None) -> bool:
    """Return whether a secret is present without exposing it."""
    if not value:
        return False
    try:
        return bool(decrypt_secret(value))
    except ValueError:
        return True


def is_encrypted_secret(value: str | None) -> bool:
    """Return whether a stored secret is already encrypted."""
    return bool(value and value.startswith(_FERNET_PREFIX))


def _fernet() -> Fernet:
    if not settings.SECRET_KEY:
        raise ValueError("SECRET_KEY must be configured before storing API keys")
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)
