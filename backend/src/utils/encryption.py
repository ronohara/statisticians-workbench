"""
Encryption utilities for the Workbench backend.
Uses AES-256-GCM for field encryption.
"""
import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

# Module-level decrypt for simple field decryption (uses ENCRYPTION_KEY)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY or len(ENCRYPTION_KEY) != 64:
    load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    if not ENCRYPTION_KEY or len(ENCRYPTION_KEY) != 64:
        raise RuntimeError("ENCRYPTION_KEY must be a 32-byte hex string (64 chars)")

ENCRYPTION_KEY_BYTES = bytes.fromhex(ENCRYPTION_KEY)


def decrypt_field(encrypted_text: str) -> str:
    """Decrypt a field using ENCRYPTION_KEY (legacy)."""
    try:
        parts = encrypted_text.split(":")
        if len(parts) != 3:
            raise ValueError("Invalid encrypted format")
        iv = base64.b64decode(parts[0])
        auth_tag = base64.b64decode(parts[1])
        encrypted = base64.b64decode(parts[2])
        aesgcm = AESGCM(ENCRYPTION_KEY_BYTES)
        decrypted = aesgcm.decrypt(iv, encrypted + auth_tag, None)
        return decrypted.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")


def encrypt_field(text: str) -> str:
    """AES-256-GCM, iv:authTag:ciphertext base64 — byte-compatible with
    @/lib/encryption on the Next.js side."""
    iv = secrets.token_bytes(16)
    aesgcm = AESGCM(ENCRYPTION_KEY_BYTES)
    encrypted = aesgcm.encrypt(iv, text.encode("utf-8"), None)
    auth_tag = encrypted[-16:]
    ciphertext = encrypted[:-16]
    return (base64.b64encode(iv).decode("ascii")
            + ":" + base64.b64encode(auth_tag).decode("ascii")
            + ":" + base64.b64encode(ciphertext).decode("ascii"))


def decrypt_field_or_null(encrypted: str) -> str | None:
    """Decrypt a field, returning None when absent or when decryption fails.

    Mirrors the frontend's decryptPassword/decryptApiKey (null-on-failure)
    rather than the raising decrypt_field above.
    """
    if not encrypted:
        return None
    try:
        parts = encrypted.split(":")
        if len(parts) != 3:
            raise ValueError("Invalid encrypted format")
        iv = base64.b64decode(parts[0])
        auth_tag = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        aesgcm = AESGCM(ENCRYPTION_KEY_BYTES)
        return aesgcm.decrypt(iv, ciphertext + auth_tag, None).decode("utf-8")
    except Exception:
        return None
