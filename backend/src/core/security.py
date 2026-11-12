from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src.core.config import get_settings
from src.core.db import User

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, password)
    except VerifyMismatchError:
        return False


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.utcnow()
    claims = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "tenant_id": str(user.id),
        "scopes": [user.role],
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
