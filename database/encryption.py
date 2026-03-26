"""
Database encryption utilities — AES-256 via Fernet for biometric embeddings.
"""
import base64
import json
import os
from cryptography.fernet import Fernet

# Generate a persistent key — in production, load from secure vault
_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "encryption.key")

def _get_or_create_key() -> bytes:
    os.makedirs(os.path.dirname(_KEY_FILE), exist_ok=True)
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(_KEY_FILE, "wb") as f:
        f.write(key)
    return key

_fernet = Fernet(_get_or_create_key())

def encrypt_embedding(embedding: list[float]) -> str:
    """Encrypt a face embedding vector. Returns base64 string."""
    raw = json.dumps(embedding).encode()
    return _fernet.encrypt(raw).decode()

def decrypt_embedding(token: str) -> list[float]:
    """Decrypt a face embedding vector."""
    raw = _fernet.decrypt(token.encode())
    return json.loads(raw)

def encrypt_text(text: str) -> str:
    """Encrypt sensitive text field."""
    return _fernet.encrypt(text.encode()).decode()

def decrypt_text(token: str) -> str:
    """Decrypt sensitive text field."""
    return _fernet.decrypt(token.encode()).decode()
