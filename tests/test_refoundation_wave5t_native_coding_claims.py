from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_PUBLIC_SYMBOLS = (
    "ClaimMode",
    "ClaimStatus",
    "CodeClaim",
    "CodeClaimLedger",
)


def test_wave5t_canonical_coding_claims_owns_complete_public_implementation() -> None:
    import nolane.external_core.coding_claims as canonical

    assert all(
        getattr(canonical, name).__module__ == "nolane.external_core.coding_claims"
        for name in _PUBLIC_SYMBOLS
    )
    assert canonical.COMPONENT_ID == "external.coding.claims"
    assert canonical.COMPONENT_VERSION == "0.0.2"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.code_claims"


def test_wave5t_historical_coding_claims_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.code_claims as legacy
    import nolane.external_core.coding_claims as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5t_canonical_coding_claims_has_no_reverse_authority_import() -> None:
    import nolane.external_core.coding_claims as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.code_claims" or alias.name.startswith(
                    "cogcoder.organization.code_claims."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.code_claims" or module.startswith(
                "cogcoder.organization.code_claims."
            ):
                offenders.append(f"from:{node.lineno}:{module}")

    assert offenders == [], (
        "canonical coding-claims authority reverse-imports historical implementation: "
        + "; ".join(offenders)
    )


def test_wave5t_claim_scope_conflicts_coverage_release_and_round_trip_remain_fail_closed() -> None:
    from nolane.external_core.coding_claims import (
        ClaimMode,
        ClaimStatus,
        CodeClaimLedger,
    )

    ledger = CodeClaimLedger()
    root_claim = ledger.claim(
        agent_id="coding.impl.1",
        task_id="task-5t",
        directory_prefixes=("src/pkg",),
    )
    same_owner = ledger.claim(
        agent_id="coding.impl.1",
        task_id="task-5t",
        file_paths=("src/pkg/a.py",),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )

    assert root_claim.claim_id == "claim-00000001"
    assert same_owner.claim_id == "claim-00000002"
    assert ledger.covers(
        agent_id="coding.impl.1",
        task_id="task-5t",
        file_paths=("src/pkg/a.py", "src/pkg/nested/b.py"),
        symbol_ids=(),
    )
    assert not ledger.covers(
        agent_id="coding.impl.1",
        task_id="other-task",
        file_paths=("src/pkg/a.py",),
        symbol_ids=(),
    )

    with pytest.raises(PermissionError, match="exclusive code scope conflicts"):
        ledger.claim(
            agent_id="coding.impl.2",
            task_id="task-5t",
            file_paths=("src/pkg/nested/c.py",),
        )

    with pytest.raises(PermissionError, match="claim release requires owner"):
        ledger.release(root_claim.claim_id, actor_agent_id="coding.impl.2")

    released = ledger.release(root_claim.claim_id, actor_agent_id="coding.chief")
    assert released.status is ClaimStatus.RELEASED
    assert ledger.get(root_claim.claim_id) == released

    restored = CodeClaimLedger.from_state(ledger.to_state())
    assert restored.to_state() == ledger.to_state()
    assert restored.get(same_owner.claim_id) == same_owner


def test_wave5t_claim_paths_and_snapshot_conflicts_reject_noncanonical_state() -> None:
    from nolane.external_core.coding_claims import CodeClaim, CodeClaimLedger

    with pytest.raises(ValueError, match="repository-relative"):
        CodeClaim.from_state(
            {
                "claim_id": "claim-00000001",
                "agent_id": "coding.impl.1",
                "task_id": "task-5t",
                "file_paths": ["../escape.py"],
            }
        )

    snapshot = {
        "counter": 2,
        "claims": [
            {
                "claim_id": "claim-00000001",
                "agent_id": "coding.impl.1",
                "task_id": "task-5t",
                "file_paths": ["src/shared.py"],
                "symbol_ids": [],
                "directory_prefixes": [],
                "mode": "exclusive_write",
                "status": "active",
            },
            {
                "claim_id": "claim-00000002",
                "agent_id": "coding.impl.2",
                "task_id": "task-5t",
                "file_paths": ["src/shared.py"],
                "symbol_ids": [],
                "directory_prefixes": [],
                "mode": "exclusive_write",
                "status": "active",
            },
        ],
    }
    with pytest.raises(ValueError, match="conflicting active exclusive code claims"):
        CodeClaimLedger.from_state(snapshot)


def test_wave5t_coding_claims_component_version_and_authority_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["external.coding.claims"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.coding_claims"
    assert row.legacy_sources == ("cogcoder/organization/code_claims.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.2"
    assert str(component_version("external.coding.claims")) == "0.0.2"


def test_wave5t_generated_native_debt_no_longer_contains_coding_claims() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.coding.claims" not in serialized

    implementation = build_component_implementation_ledger()
    non_native = [
        row
        for row in implementation.values()
        if row.status is not ImplementationStatus.CANONICAL_NATIVE
    ]
    assert len(non_native) <= 26


def test_wave5t_current_status_tracks_coding_claims_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5T" in status
    assert "`external.coding.claims` -> native `nolane.external_core.coding_claims`" in status
