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
from nolane.evaluation.regimes import (
    BenchmarkDomain,
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
    EvaluationMode,
)
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry
from nolane.schemas.identity import AgentIdentity, AgentRank, ParameterAccounting


_PUBLIC_SYMBOLS = (
    "EvaluationObservation",
    "MatchedBudgetComparison",
    "OrganizationSuperiorityAssessment",
    "AblationAssessment",
    "EvaluationEvidenceLedger",
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


def _behavior_fixture() -> tuple[AgentRegistry, BenchmarkRegimeRegistry, EvidenceRecord]:
    verifier = AgentIdentity(
        agent_id="wave5ag-verifier",
        name="Wave 5AG Verifier",
        region="evaluation",
        role="evaluation verifier",
        rank=AgentRank.SPECIALIST,
        neural_version="neural-test-0.1",
        parameter_accounting=ParameterAccounting(1, 1),
        region_chief_id="evaluation-chief",
        direct_work_capable=True,
        learning_capable=True,
        cognitive_capabilities=("verification",),
        memory_namespace="memory.wave5ag-verifier",
        skill_namespace="skills.wave5ag-verifier",
    )
    registry = AgentRegistry((verifier,))
    regimes = BenchmarkRegimeRegistry()
    regimes.register(
        regime_id="wave5ag-matched-budget",
        benchmark_id="wave5ag-benchmark",
        domain=BenchmarkDomain.CODING,
        task_set_digest="task-set-wave5ag",
        repository_revision_digest="repository-wave5ag",
        tool_envelope_digest="tools-wave5ag",
        compute_budget_units=100,
        tool_call_budget=10,
        external_core_budget=5,
        wall_clock_budget_ms=1_000,
        active_agent_budget=4,
        freshness_epoch=1,
        evaluator_protocol_version="evaluation-protocol-0.1",
        provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
        fresh=True,
        heldout=True,
    )
    evidence = EvidenceRecord(
        evidence_id="wave5ag-clean-evidence",
        verifier_agent_id=verifier.agent_id,
        passed=True,
        false_accepts=0,
        regressions=0,
        notes="representative native evaluation evidence behavior contract",
    )
    return registry, regimes, evidence


def test_wave5ag_canonical_module_owns_evaluation_evidence_authority() -> None:
    import nolane.evaluation.evidence as canonical

    assert canonical.COMPONENT_ID == "evaluation.evidence"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_evidence"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.evidence"


def test_wave5ag_historical_evidence_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_evidence as legacy
    import nolane.evaluation.evidence as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ag_canonical_evidence_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "evidence.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.organization.identity" in imports
    assert "nolane.external_core.evidence" in imports
    assert "nolane.core.canonical_digest" in imports
    assert "nolane.evaluation.regimes" in imports


def test_wave5ag_native_evidence_preserves_roundtrip_and_matched_budget_behavior() -> None:
    registry, regimes, evidence = _behavior_fixture()
    ledger = EvaluationEvidenceLedger(registry=registry, regimes=regimes)

    organization = ledger.record_observation(
        observation_id="wave5ag-organization",
        regime_id="wave5ag-matched-budget",
        mode=EvaluationMode.ORGANIZATION,
        producer_revision="organization-revision",
        score=0.8,
        task_count=10,
        pass_count=8,
        false_accepts=0,
        regressions=0,
        compute_units=80,
        tool_calls=8,
        external_core_calls=4,
        wall_clock_ms=800,
        energy_joules=2.5,
        active_agents=4,
        evidence_artifact_ids=("artifact-organization",),
        evidence=evidence,
    )
    baseline = ledger.record_observation(
        observation_id="wave5ag-single-agent",
        regime_id="wave5ag-matched-budget",
        mode=EvaluationMode.SINGLE_AGENT,
        producer_revision="single-agent-revision",
        score=0.7,
        task_count=10,
        pass_count=7,
        false_accepts=0,
        regressions=0,
        compute_units=80,
        tool_calls=8,
        external_core_calls=4,
        wall_clock_ms=800,
        energy_joules=2.0,
        active_agents=1,
        evidence_artifact_ids=("artifact-single-agent",),
        evidence=evidence,
    )

    comparison = ledger.compare_matched_budget(organization.observation_id, baseline.observation_id)
    assert comparison.comparable
    assert comparison.improved
    assert comparison.score_delta > 0
    assert comparison.reason == "clean_matched_budget_improvement"

    state = ledger.to_state()
    restored = EvaluationEvidenceLedger.from_state(registry=registry, regimes=regimes, state=state)
    assert restored.to_state() == state
    assert restored.get_observation(organization.observation_id) == organization
    assert restored.get_comparison(comparison.comparison_id) == comparison


def test_wave5ag_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.evidence"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.evidence"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.evidence")) == "0.0.1"
    assert all(binding.component_id != "evaluation.evidence" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.evidence" not in ids
    assert len(state["components"]) == 16


def test_wave5ag_current_status_tracks_native_evidence_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AG" in status
    assert "evaluation.evidence" in status
    assert "16 non-native" in status
