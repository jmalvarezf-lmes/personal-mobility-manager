"""
Unit tests for infrastructure/crypto.py (Fernet encrypt/decrypt helpers).

Skipped if the cryptography package is not installed.
"""

import pytest

try:
    import cryptography  # noqa: F401

    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    _CRYPTOGRAPHY_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE,
    reason="cryptography package not installed",
)


@pytest.fixture()
def fernet_key() -> bytes:
    from cryptography.fernet import Fernet

    return Fernet.generate_key()


def test_encrypt_returns_bytes(fernet_key: bytes) -> None:
    from mobility_manager.infrastructure.crypto import encrypt

    result = encrypt({"foo": "bar"}, fernet_key)
    assert isinstance(result, bytes)


def test_decrypt_round_trip(fernet_key: bytes) -> None:
    from mobility_manager.infrastructure.crypto import decrypt, encrypt

    data = {"username": "alice", "password": "s3cr3t", "locale": "en_GB", "vin": "VIN001"}
    ciphertext = encrypt(data, fernet_key)
    recovered = decrypt(ciphertext, fernet_key)

    assert recovered == data


def test_ciphertext_is_not_plaintext(fernet_key: bytes) -> None:
    from mobility_manager.infrastructure.crypto import encrypt

    data = {"password": "supersecret"}
    ciphertext = encrypt(data, fernet_key)
    assert b"supersecret" not in ciphertext


def test_wrong_key_raises(fernet_key: bytes) -> None:
    from cryptography.fernet import Fernet, InvalidToken

    from mobility_manager.infrastructure.crypto import decrypt, encrypt

    ciphertext = encrypt({"a": 1}, fernet_key)
    wrong_key = Fernet.generate_key()

    with pytest.raises(InvalidToken):
        decrypt(ciphertext, wrong_key)


def test_tampered_ciphertext_raises(fernet_key: bytes) -> None:
    from cryptography.fernet import InvalidToken

    from mobility_manager.infrastructure.crypto import decrypt, encrypt

    ciphertext = bytearray(encrypt({"a": 1}, fernet_key))
    ciphertext[-1] ^= 0xFF  # flip last byte
    with pytest.raises(InvalidToken):
        decrypt(bytes(ciphertext), fernet_key)
