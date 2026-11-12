"""Idempotent one-off seed for the initial admin account and the public
"demo_user" account used by the portfolio Login page's Demo Access card.

Run manually from the backend venv (not part of the Alembic migration, so
credentials never live in migration history):

    cd backend
    .venv\\Scripts\\Activate.ps1
    $env:ADMIN_PASSWORD = "ChangeMe123!"
    python -m src.scripts.seed_users
"""

import logging
import os
import sys

from src.core.db import SessionLocal, User
from src.core.security import hash_password

logger = logging.getLogger(__name__)

# Deliberately small so a portfolio visitor hits the quota UX within a
# couple minutes of exploring the demo.
DEMO_LLM_REQUEST_LIMIT = 15
DEMO_UPLOAD_LIMIT = 5

# Admins are exempt from quota enforcement (see src/api/quota.py) — these
# numbers are effectively unused, kept generous just in case that changes.
ADMIN_LLM_REQUEST_LIMIT = 100_000
ADMIN_UPLOAD_LIMIT = 100_000


def _ensure_user(username: str, password: str, role: str, llm_request_limit: int, upload_limit: int) -> None:
    with SessionLocal() as db:
        existing = db.query(User).filter(User.username == username).first()
        if existing is not None:
            print(f"User '{username}' already exists, skipping.")
            return

        db.add(
            User(
                username=username,
                hashed_password=hash_password(password),
                role=role,
                llm_request_limit=llm_request_limit,
                upload_limit=upload_limit,
            )
        )
        db.commit()
        print(f"Created {role} user '{username}'.")


def main() -> None:
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        print("ADMIN_PASSWORD env var is required (no default — this becomes a real credential).", file=sys.stderr)
        raise SystemExit(1)

    demo_username = os.environ.get("DEMO_USERNAME", "demo_user")
    demo_password = os.environ.get("DEMO_PASSWORD", "demo123")

    _ensure_user(admin_username, admin_password, "admin", ADMIN_LLM_REQUEST_LIMIT, ADMIN_UPLOAD_LIMIT)
    _ensure_user(demo_username, demo_password, "user", DEMO_LLM_REQUEST_LIMIT, DEMO_UPLOAD_LIMIT)


if __name__ == "__main__":
    main()
