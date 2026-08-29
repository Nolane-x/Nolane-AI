from __future__ import annotations

import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_wave5ay_transfer_meta_authority_version_provenance_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.transfer_meta"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.transfer_meta"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.transfer_meta")) == "0.0.1"
    assert row.legacy_sources == (
        "cogcoder/r269_causal_basis_adapter.py",
        "cogcoder/r269_experience_compiler.py",
        "cogcoder/r269_transfer_runtime.py",
    )

    debt = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    assert debt["schema_version"] == "nolane-native-debt-v2"
    assert debt["actionable_migration_debt_count"] == 0
    assert debt["accepted_non_migration_count"] == 1
    assert debt["counts_by_status"] == {"frozen_asset": 1}
    assert [record["component_id"] for record in debt["components"]] == ["neural.shared"]
    remaining = debt["components"][0]
    assert remaining["implementation_status"] == "frozen_asset"
    assert remaining["migration_action_required"] is False
    assert remaining["canonical_module"] is None
    assert not remaining["canonical_write_authority"]
    assert remaining["legacy_sources"] == ["model/neural-r2.3"]

    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AY" in status
    assert "external.transfer_meta" in status
    assert "moves from 2 to 1 non-native" in status
    assert "historical_only` debt reaches zero" in status

    carrier = _root() / ".github" / "workflows" / "refoundation-wave5ay-metadata-cutover-carrier.yml"
    assert not carrier.exists()
