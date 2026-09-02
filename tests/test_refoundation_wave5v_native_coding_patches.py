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
    "CodingPatchStatus",
    "ToolInvocationReceipt",
    "PatchProvenanceEnvelope",
    "PatchTransitionReceipt",
    "CodingPatchCandidate",
    "CodingPatchLedger",
)


def test_wave5v_canonical_coding_patches_owns_complete_public_implementation() -> None:
    import nolane.external_core.coding_patches as canonical

    assert all(
        getattr(canonical, name).__module__ == "nolane.external_core.coding_patches"
        for name in _PUBLIC_SYMBOLS
    )
    assert canonical.COMPONENT_ID == "external.coding.patches"
    assert canonical.COMPONENT_VERSION == "0.0.2"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.coding_patches"


def test_wave5v_historical_coding_patches_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.coding_patches as legacy
    import nolane.external_core.coding_patches as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5v_canonical_coding_patches_has_only_canonical_runtime_dependencies() -> None:
    import nolane.external_core.coding_patches as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    historical: list[str] = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                if alias.name.startswith("cogcoder.organization"):
                    historical.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
            if module.startswith("cogcoder.organization"):
                historical.append(f"from:{node.lineno}:{module}")

    assert historical == []
    assert "nolane.external_core.coding_claims" in imports
    assert "nolane.core.canonical_digest" in imports


def test_wave5v_patch_scope_status_claim_coverage_and_path_validation_are_preserved() -> None:
    from nolane.external_core.coding_claims import CodeClaimLedger
    from nolane.external_core.coding_patches import (
        CodingPatchCandidate,
        CodingPatchLedger,
        CodingPatchStatus,
    )

    claims = CodeClaimLedger()
    claims.claim(
        agent_id="coding.impl.1",
        task_id="task-5v",
        directory_prefixes=("src/pkg",),
        symbol_ids=("A.run",),
    )
    patches = CodingPatchLedger(claims)
    patch = patches.register_patch(
        producer_agent_id="coding.impl.1",
        task_id="task-5v",
        work_id="work-5v",
        base_plan_version=7,
        base_architecture_version=4,
        touched_files=("./src/pkg/a.py", "src/pkg/a.py"),
        touched_symbols=("A.run", "A.run"),
        patch_artifact_id="artifact-patch-5v",
        compile_evidence_refs=("compile-5v",),
        test_evidence_refs=("test-5v",),
    )

    assert patch.patch_id == "patch-00000001"
    assert patch.touched_files == ("src/pkg/a.py",)
    assert patch.touched_symbols == ("A.run",)
    assert patch.status is CodingPatchStatus.EVIDENCE_READY
    assert patches.claim_coverage(patch.patch_id)
    with pytest.raises(PermissionError, match="verified"):
        patches.set_status(patch.patch_id, CodingPatchStatus.VERIFIED)
    assert patches.set_status(patch.patch_id, CodingPatchStatus.REJECTED).status is CodingPatchStatus.REJECTED

    with pytest.raises(ValueError, match="repository-relative"):
        CodingPatchCandidate.from_state(
            {
                **patch.to_state(),
                "touched_files": ["../escape.py"],
            }
        )


def test_wave5v_tool_receipts_are_content_addressed_and_fail_closed() -> None:
    from nolane.external_core.coding_claims import CodeClaimLedger
    from nolane.external_core.coding_patches import CodingPatchLedger, ToolInvocationReceipt

    patches = CodingPatchLedger(CodeClaimLedger())
    first = patches.record_tool_invocation(
        agent_id="coding.systems.01",
        task_id="task-5v",
        tool_id="compiler",
        output_artifact_refs=("artifact-build-5v",),
        success=True,
        evidence_refs=("evidence-tool-5v",),
    )
    second = patches.record_tool_invocation(
        agent_id="coding.systems.01",
        task_id="task-5v",
        tool_id="compiler",
        output_artifact_refs=("artifact-build-5v",),
        success=True,
        evidence_refs=("evidence-tool-5v",),
    )
    assert second == first
    assert patches.get_tool_receipt(first.receipt_id) == first

    tampered = first.to_state()
    tampered["success"] = False
    with pytest.raises(ValueError, match="tool invocation receipt digest/id mismatch"):
        ToolInvocationReceipt.from_state(tampered)


def test_wave5v_patch_ledger_state_round_trip_and_counter_validation_are_fail_closed() -> None:
    from nolane.external_core.coding_claims import CodeClaimLedger
    from nolane.external_core.coding_patches import CodingPatchLedger

    claims = CodeClaimLedger()
    patches = CodingPatchLedger(claims)
    patches.register_patch(
        producer_agent_id="coding.impl.1",
        task_id="task-5v",
        work_id="work-5v",
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=("src/a.py",),
        patch_artifact_id="artifact-patch-5v",
    )
    patches.record_tool_invocation(
        agent_id="coding.impl.1",
        task_id="task-5v",
        tool_id="test-runner",
        success=True,
    )
    state = patches.to_state()
    restored = CodingPatchLedger.from_state(claims=claims, state=state)
    assert restored.to_state() == state

    invalid = dict(state)
    invalid["patch_counter"] = 0
    with pytest.raises(ValueError, match="patch counter is behind patch history"):
        CodingPatchLedger.from_state(claims=claims, state=invalid)


def test_wave5v_coding_patches_component_version_authority_and_debt_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["external.coding.patches"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.coding_patches"
    assert row.legacy_sources == ("cogcoder/organization/coding_patches.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.2"
    assert str(component_version("external.coding.patches")) == "0.0.2"

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.coding.patches" not in serialized

    non_native = [
        record
        for record in implementation.values()
        if record.status is not ImplementationStatus.CANONICAL_NATIVE
    ]
    assert len(non_native) <= 25


def test_wave5v_current_status_tracks_coding_patch_cutover_and_executor_prerequisite() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5V" in status
    assert "`external.coding.patches` -> native `nolane.external_core.coding_patches`" in status
    assert "executor" in status.lower()
