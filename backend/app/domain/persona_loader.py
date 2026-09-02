"""Loads persona configuration from the same source files the CLI reference uses.

Intentionally reads ``profile/persona.yml`` and ``profile/facts.yml`` directly (not a
duplicated copy) so both the CLI (``automation/``) and this backend stay in sync
until Phase 1's DB migration seeds ``persona_config``/``knowledge_items`` from these
same files (see architecture-assessment.md § D) and callers move to the repository
layer instead.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
PERSONA_PATH = ROOT / "profile" / "persona.yml"
FACTS_PATH = ROOT / "profile" / "facts.yml"
WEIGHTS_PATH = ROOT / "automation" / "learning" / "weights.yml"


def load_persona() -> dict:
    return yaml.safe_load(PERSONA_PATH.read_text(encoding="utf-8"))


def load_facts() -> dict:
    return yaml.safe_load(FACTS_PATH.read_text(encoding="utf-8"))


def load_learning() -> dict:
    """Learning weights (TRD § 10): {pillar: multiplier}. 1.0 = neutral."""
    if WEIGHTS_PATH.exists():
        data = yaml.safe_load(WEIGHTS_PATH.read_text(encoding="utf-8")) or {}
        return data.get("pillar_multipliers", {}) or {}
    return {}
