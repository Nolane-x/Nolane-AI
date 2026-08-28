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
from nolane.evaluation.evidence import EvaluationEvidenceLedger
from nolane.evaluation.parameters import ParameterScalingAuthority
from nolane.evaluation.regimes import BenchmarkRegimeRegistry
from nolane.organization.identity import AgentRegistry
from nolane.schemas.identity import AgentIdentity, AgentRank, ParameterAccounting


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


def _agent(agent_id: str, *, region: str, local_parameters: int) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        name=f"Wave 5AH {agent_id}",
        region=region,
        role="parameter accounting fixture",
        rank=AgentRank.SPECIALIST,
        neural_version="neural-test-0.1",
        parameter_accounting=ParameterAccounting(10, local_parameters),
        region_chief_id=f"{region}-chief",
        direct_work_capable=True,
        learning_capable=True,
        cognitive_capabilities=("parameter_accounting",),
        memory_namespace=f"memory.{agent_id}",
        skill_namespace=f"skills.{agent_id}",
    )


def _behavior_fixture() -> tuple[AgentRegistry, EvaluationEvidenceLedger]:
    registry = AgentRegistry(
        (
            _agent("wave5ah-alpha", region="evaluation-alpha", local_parameters=2),
            _agent("wave5ah-beta", region="evaluation-beta", local_parameters=3),
        )
    )
    regimes = BenchmarkRegimeRegistry()
    evidence = EvaluationEvidenceLedger(registry=registry, regimes=regimes)
    return registry, evidence


def test_wave5ah_canonical_module_owns_evaluation_parameters_authority() -> None:
    import nolane.evaluation.parameters as canonical

    assert canonical.COMPONENT_ID == "evaluation.parameters"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_parameters"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.parameters"


def test_wave5ah_historical_parameters_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_parameters as legacy
    import nolane.evaluation.parameters as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ah_canonical_parameters_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "parameters.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.evaluation.evidence" in imports
    assert "nolane.evaluation.regimes" in imports
    assert "nolane.organization.identity" in imports
    assert "nolane.core.canonical_digest" in imports


def test_wave5ah_native_parameters_preserves_footprint_and_state_roundtrip() -> None:
    registry, evidence = _behavior_fixture()
    authority = ParameterScalingAuthority(registry=registry, evidence=evidence)

    report = authority.parameter_footprint(
        active_agent_ids=("wave5ah-alpha", "wave5ah-beta"),
        active_ephemeral_count=2,
        compute_units=100,
        latency_ms=50,
        energy_joules=1.5,
    )

    assert report.shared_physical_parameters == 10
    assert report.local_physical_parameters == 5
    assert report.unique_stored_physical_parameters == 15
    assert report.active_inference_physical_parameters == 15
    assert report.logical_deployed_parameter_footprint == 25

    state = authority.to_state()
    restored = ParameterScalingAuthority.from_state(registry=registry, evidence=evidence, state=state)
    assert restored.to_state() == state
    assert restored.get_report(report.report_id) == report


def test_wave5ah_authority_version_facade_and_debt_cutover() -> None:
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
    assert len(state["components"]) == 15


def test_wave5ah_current_status_tracks_native_parameters_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AH" in status
    assert "evaluation.parameters" in status
    assert "15 non-native" in status
