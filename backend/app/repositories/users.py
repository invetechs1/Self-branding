"""Repository for `users` — dashboard login accounts.

Passwords are bcrypt-hashed at rest (never stored or logged in plaintext,
per the brief's security rules). `verify_password` runs a constant-time
comparison via bcrypt itself — no custom comparison logic to get wrong.
"""

from __future__ import annotations

from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False  # malformed hash — never crash the login endpoint on bad data


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_or_update(self, email: str, plain_password: str) -> User:
        email = email.strip().lower()
        existing = self.session.scalar(select(User).where(User.email == email))
        password_hash = hash_password(plain_password)
        if existing:
            existing.password_hash = password_hash
            return existing
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        return user

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email.strip().lower()))

    def authenticate(self, email: str, plain_password: str) -> User | None:
        user = self.get_by_email(email)
        if user is None:
            # still run a hash comparison against a dummy value so a bad email
            # and a bad password take the same amount of time (no user-enumeration
            # timing side channel)
            verify_password(plain_password, hash_password("dummy-constant-time-padding"))
            return None
        if not verify_password(plain_password, user.password_hash):
            return None
        user.last_login_at = datetime.now(timezone.utc)
        return user
