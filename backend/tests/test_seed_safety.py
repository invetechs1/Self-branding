"""Guards the brief's non-negotiable rule 5 ("NOTHING AUTO-PUBLISHES" for the first
three months) at the schema-seed level. architecture-assessment.md's risk table
calls for exactly this: a build-breaking check if the seeded default ever flips."""

import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "db" / "migrations" / "0001_init.sql"


def test_auto_publish_green_seeds_false():
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"'auto_publish_green',\s*'(true|false)'::jsonb", sql)
    assert match is not None, "auto_publish_green seed row not found in migration"
    assert match.group(1) == "false", "auto_publish_green must seed as false (brief rule 5)"


def test_require_approval_seeds_true():
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"'require_approval',\s*'(true|false)'::jsonb", sql)
    assert match is not None, "require_approval seed row not found in migration"
    assert match.group(1) == "true", "require_approval must seed as true (brief rule 5)"
