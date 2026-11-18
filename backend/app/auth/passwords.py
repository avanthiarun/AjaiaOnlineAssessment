"""Password hashing with bcrypt."""

import bcrypt


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of the password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())
