#!/usr/bin/env python3
"""Creates or updates a dashboard login account. Idempotent — re-running with
the same email updates that user's password.

    python scripts/create_user.py --email yahya@bassir.net --password 'Bassir@20302030'

Never pass a password on the command line in a shared/logged environment —
prefer running this interactively. Requires db/migrations/0002_users.sql to
already be applied.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import SessionLocal
from app.repositories.users import UserRepository


def main() -> None:
    ap = argparse.ArgumentParser(description="create or update a dashboard login account")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()

    session = SessionLocal()
    try:
        user = UserRepository(session).create_or_update(args.email, args.password)
        session.commit()
        print(f"User ready: {user.email}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
