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
    "ParameterFootprintReport",
    "ScalingDecision",
    "ScalingProposal",
    "ScalingDecisionReceipt",
    "ParameterScalingAuthority",
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


def test_wave5aj_canonical_module_owns_evaluation_parameters_authority() -> None:
    import nolane.evaluation.parameters as canonical

    assert canonical.COMPONENT_ID == "evaluation.parameters"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_parameters"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.parameters"


def test_wave5aj_historical_parameters_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_parameters as legacy
    import nolane.evaluation.parameters as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5aj_canonical_parameters_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "parameters.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.evaluation.evidence" in imports
    assert "nolane.evaluation.regimes" in imports
    assert "nolane.organization.identity" in imports
    assert "nolane.core.canonical_digest" in imports


def test_wave5aj_parameter_receipts_preserve_state_and_digest_behavior() -> None:
    from nolane.evaluation.parameters import (
        ParameterFootprintReport,
        ScalingDecision,
        ScalingDecisionReceipt,
    )

    footprint_payload = {
        "report_id": "wave5aj-footprint",
        "active_agent_ids": ["agent-a"],
        "active_ephemeral_count": 0,
        "shared_physical_parameters": 10,
        "local_physical_parameters": 2,
        "unique_stored_physical_parameters": 12,
        "active_inference_physical_parameters": 12,
        "logical_deployed_parameter_footprint": 12,
        "compute_units": 4,
        "latency_ms": 3,
        "energy_joules": 1.5,
    }
    footprint = ParameterFootprintReport.from_state(
        {**footprint_payload, "digest": canonical_digest(footprint_payload)}
    )
    assert footprint.to_state() == {**footprint_payload, "digest": canonical_digest(footprint_payload)}

    decision_payload = {
        "decision_id": "wave5aj-decision",
        "proposal_id": "wave5aj-proposal",
        "decision": ScalingDecision.REJECTED.value,
        "score_delta": 0.0,
        "reasons": ["insufficient_marginal_gain"],
        "verifier_regions": ["evaluation", "verification"],
    }
    decision = ScalingDecisionReceipt.from_state(
        {**decision_payload, "digest": canonical_digest(decision_payload)}
    )
    assert decision.to_state() == {**decision_payload, "digest": canonical_digest(decision_payload)}


def test_wave5aj_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.parameters"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.parameters"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.parameters")) == "0.0.1"
    assert all(binding.component_id != "evaluation.parameters" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.parameters" not in ids
    assert len(state["components"]) == 13
