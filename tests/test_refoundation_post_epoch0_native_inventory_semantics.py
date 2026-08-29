from __future__ import annotations

import json
from pathlib import Path

from nolane.repository.audit import build_native_debt, render_native_debt_markdown


ROOT = Path(__file__).resolve().parents[1]


def test_non_native_projection_distinguishes_inventory_from_actionable_migration_debt() -> None:
    payload = build_native_debt()

    assert payload["schema_version"] == "nolane-native-debt-v2"
    assert "broad non-native implementation inventory" in payload["definition"]
    assert "migration_action_required=true" in payload["definition"]
    assert payload["actionable_migration_debt_count"] == 0
    assert payload["accepted_non_migration_count"] == 1
    assert payload["counts_by_status"] == {"frozen_asset": 1}

    assert len(payload["components"]) == 1
    frozen = payload["components"][0]
    assert frozen["component_id"] == "neural.shared"
    assert frozen["implementation_status"] == "frozen_asset"
    assert frozen["migration_action_required"] is False
    assert frozen["canonical_write_authority"] is False


def test_generated_native_debt_view_states_terminal_frozen_asset_semantics() -> None:
    payload = build_native_debt()
    markdown = render_native_debt_markdown(payload)

    assert markdown.startswith("# Non-Native Implementation Inventory\n")
    assert "Actionable migration debt: `0`" in markdown
    assert "Accepted non-migration records: `1`" in markdown
    assert "Migration action required: `false`" in markdown
    assert "Frozen assets can be accepted terminal records" in markdown
    assert "makes remaining migration work impossible to hide" not in markdown


def test_committed_native_inventory_projection_matches_machine_semantics() -> None:
    committed = json.loads((ROOT / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    assert committed == build_native_debt()

    markdown = (ROOT / "CURRENT" / "NATIVE_DEBT.md").read_text(encoding="utf-8")
    assert markdown == render_native_debt_markdown(committed)
