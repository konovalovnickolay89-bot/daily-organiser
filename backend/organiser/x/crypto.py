"""Seal X tokens before they touch the database. The plaintext is not logged."""

from cryptography.fernet import Fernet, InvalidToken


class TokenKeyError(Exception):
    """The house key is missing or the ciphertext cannot be opened."""


def key_ok(raw: str) -> bool:
    text = raw.strip()
    if not text:
        return False
    try:
        Fernet(text.encode("ascii"))
    except (ValueError, TypeError):
        return False
    return True


def _fernet(raw: str) -> Fernet:
    text = raw.strip()
    try:
        return Fernet(text.encode("ascii"))
    except (ValueError, TypeError):
        raise TokenKeyError("X token key is not a Fernet key.") from None


def seal(raw_key: str, value: str) -> str:
    return _fernet(raw_key).encrypt(value.encode()).decode("ascii")


def open_sealed(raw_key: str, token: str) -> str:
    try:
        return _fernet(raw_key).decrypt(token.encode("ascii")).decode()
    except (InvalidToken, TokenKeyError, UnicodeError):
        raise TokenKeyError("Stored X token could not be opened.") from None
