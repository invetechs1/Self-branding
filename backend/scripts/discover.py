#!/usr/bin/env python3
"""Runs one discovery cycle against the database — the DB-backed equivalent of
``automation/news_engine.py --discover``.

    python scripts/discover.py
    python scripts/discover.py --limit 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import SessionLocal
from app.services.discovery import run_discovery_cycle


def main() -> None:
    ap = argparse.ArgumentParser(description="discovery cycle (DB-backed)")
    ap.add_argument("--limit", type=int, default=25, help="max entries read per feed")
    args = ap.parse_args()

    session = SessionLocal()
    try:
        result = run_discovery_cycle(session, limit_per_feed=args.limit)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"Fetched {result.fetched} entries, {result.new} new, {result.kept} crossed the "
         f"relevance threshold, grouped into {result.clusters} story clusters.")
    for outcome in result.feed_outcomes:
        status = f"FAIL ({outcome.error})" if outcome.error else f"OK ({outcome.count})"
        print(f"  {status:24} {outcome.name}")


if __name__ == "__main__":
    main()
