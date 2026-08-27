from __future__ import annotations

import ast
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.core.canonical_digest import canonical_digest


_PUBLIC_SYMBOLS = (
    "EvaluationReleaseReceipt",
    "ReproductionReceipt",
    "EvaluationReleaseLedger",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_wave5ak_canonical_module_owns_evaluation_release_authority() -> None:
    import nolane.evaluation.release as canonical

    assert canonical.COMPONENT_ID == "evaluation.release"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_release"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.release"


def test_wave5ak_historical_release_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_release as legacy
    import nolane.evaluation.release as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ak_canonical_release_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "release.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.external_core.artifacts" in imports
    assert "nolane.evaluation.evidence" in imports
    assert "nolane.evaluation.parameters" in imports
    assert "nolane.evaluation.regimes" in imports
    assert "nolane.evaluation.stress" in imports
    assert "nolane.organization.identity" in imports
    assert "nolane.core.canonical_digest" in imports


def test_wave5ak_release_and_reproduction_state_roundtrip_behavior() -> None:
    from nolane.evaluation.release import EvaluationReleaseReceipt, ReproductionReceipt

    release_payload = {
        "release_id": "wave5ak-release",
        "release_version": "0.0.1",
        "source_commit_sha": "a" * 40,
        "regime_ids": ["regime-a"],
        "observation_ids": ["obs-a"],
        "comparison_ids": ["cmp-a"],
        "stress_assessment_ids": ["stress-a"],
        "parameter_report_id": "parameter-a",
        "claim_assessment_ids": ["claim-a"],
        "scaling_decision_ids": ["scaling-a"],
        "artifact_ids": ["artifact-a"],
        "artifact_digests": ["artifact-digest-a"],
        "evaluator_protocol_version": "protocol-a",
        "independent_evaluator_ids": ["external-evaluator-a"],
        "reproduction_command_digest": "command-a",
        "environment_toolchain_digest": "environment-a",
        "created_logical_epoch": 7,
        "evaluation_digest": "evaluation-a",
    }
    release = EvaluationReleaseReceipt.from_state(
        {**release_payload, "digest": canonical_digest(release_payload)}
    )
    assert release.to_state() == {
        **release_payload,
        "digest": canonical_digest(release_payload),
    }

    reproduction_payload = {
        "reproduction_id": "wave5ak-reproduction",
        "release_id": release.release_id,
        "evaluator_id": "external-evaluator-a",
        "release_digest": release.digest,
        "artifact_digest": "artifact-digest-a",
        "evaluator_protocol_version": "protocol-a",
        "reproduction_command_digest": "command-a",
        "environment_toolchain_digest": "environment-a",
        "passed": True,
        "independent": True,
    }
    reproduction = ReproductionReceipt.from_state(
        {**reproduction_payload, "digest": canonical_digest(reproduction_payload)}
    )
    assert reproduction.to_state() == {
        **reproduction_payload,
        "digest": canonical_digest(reproduction_payload),
    }


def test_wave5ak_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.release"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.release"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.release")) == "0.0.1"
    assert all(binding.component_id != "evaluation.release" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.release" not in ids
    assert len(state["components"]) == 12
