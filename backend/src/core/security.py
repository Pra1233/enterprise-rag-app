from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src.core.config import get_settings
from src.core.db import User

# Argon2's defaults (64 MiB, time_cost=3, parallelism=4) spike memory per
# hash/verify call - fine on a normal host, but measured to OOM-kill the
# whole process on a 512MB free-tier instance already carrying a heavy
# ML import footprint (torch/transformers/langchain): GET /health (no
# hashing) stayed up reliably while POST /auth/login consistently 502'd.
# OWASP's own documented minimum profile (19 MiB, t=2, p=1) is still a
# legitimate, secure Argon2id configuration - not an ad-hoc weakening.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


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
