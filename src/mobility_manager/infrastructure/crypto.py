"""
Infrastructure: Fernet symmetric encryption helpers.

Used exclusively by PostgresVehicleConfigRepository to encrypt and decrypt
Toyota credentials before storing them in the database.

Key format: base64-encoded 32-byte key as produced by ``Fernet.generate_key()``.
"""

import json
from typing import Any

from cryptography.fernet import Fernet


def encrypt(data: dict[str, Any], key: bytes) -> bytes:
    """
    Serialise ``data`` to JSON and encrypt with Fernet (AES-128-CBC + HMAC-SHA256).

    Args:
        data: Arbitrary JSON-serialisable dict.
        key: Base64-encoded Fernet key (32 bytes).

    Returns:
        Fernet ciphertext bytes.
    """
    f = Fernet(key)
    plaintext = json.dumps(data).encode()
    return f.encrypt(plaintext)


def decrypt(ciphertext: bytes, key: bytes) -> dict[str, Any]:
    """
    Decrypt Fernet ciphertext and deserialise the JSON payload.

    Args:
        ciphertext: Fernet-encrypted bytes.
        key: Base64-encoded Fernet key (must match the key used to encrypt).

    Returns:
        Decrypted dict.

    Raises:
        cryptography.fernet.InvalidToken: If decryption fails (bad key or tampered data).
    """
    f = Fernet(key)
    plaintext = f.decrypt(ciphertext)
    result: dict[str, Any] = json.loads(plaintext.decode())
    return result
