import logging

from sqlalchemy.orm import Session

from src.api.exceptions import UnauthorizedError
from src.api.schemas.auth import LoginRequest, LoginResponse, UserOut
from src.core.config import get_settings
from src.core.db import LoginAuditLog, User
from src.core.security import create_access_token, verify_password

logger = logging.getLogger(__name__)


def login(db: Session, payload: LoginRequest, ip_address: str | None, user_agent: str | None) -> LoginResponse:
    user = db.query(User).filter(User.username == payload.username).first()

    # Same error for "no such user", "inactive", and "wrong password" — never
    # reveal which part of the credential pair was incorrect.
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("Invalid username or password.")

    db.add(
        LoginAuditLog(
            user_id=user.id,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    db.commit()

    settings = get_settings()
    return LoginResponse(
        access_token=create_access_token(user),
        expires_in=settings.jwt_expiry_hours * 3600,
        user=UserOut.model_validate(user),
    )
