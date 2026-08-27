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
from nolane.evaluation.stress import LongHorizonStressLedger
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry
from nolane.schemas.identity import AgentIdentity, AgentRank, ParameterAccounting


_PUBLIC_SYMBOLS = (
    "StressScenarioKind",
    "LongHorizonStressObservation",
    "StressSuiteAssessment",
    "LongHorizonStressLedger",
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


def _behavior_fixture() -> tuple[AgentRegistry, EvidenceRecord]:
    verifier = AgentIdentity(
        agent_id="wave5ah-verifier",
        name="Wave 5AH Verifier",
        region="evaluation",
        role="stress verifier",
        rank=AgentRank.SPECIALIST,
        neural_version="neural-test-0.1",
        parameter_accounting=ParameterAccounting(1, 1),
        region_chief_id="evaluation-chief",
        direct_work_capable=True,
        learning_capable=True,
        cognitive_capabilities=("verification",),
        memory_namespace="memory.wave5ah-verifier",
        skill_namespace="skills.wave5ah-verifier",
    )
    registry = AgentRegistry((verifier,))
    evidence = EvidenceRecord(
        evidence_id="wave5ah-clean-evidence",
        verifier_agent_id=verifier.agent_id,
        passed=True,
        false_accepts=0,
        regressions=0,
        notes="representative native evaluation stress behavior contract",
    )
    return registry, evidence


def test_wave5ah_canonical_module_owns_evaluation_stress_authority() -> None:
    import nolane.evaluation.stress as canonical

    assert canonical.COMPONENT_ID == "evaluation.stress"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_stress"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.stress"


def test_wave5ah_historical_stress_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_stress as legacy
    import nolane.evaluation.stress as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ah_canonical_stress_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "stress.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.organization.identity" in imports
    assert "nolane.external_core.evidence" in imports
    assert "nolane.core.canonical_digest" in imports


def test_wave5ah_native_stress_preserves_clean_suite_and_roundtrip_behavior() -> None:
    registry, evidence = _behavior_fixture()
    ledger = LongHorizonStressLedger(registry=registry)
    observation_ids: list[str] = []

    for index, scenario in enumerate(LongHorizonStressLedger.REQUIRED_SCENARIOS, start=1):
        row = ledger.record_stress(
            observation_id=f"wave5ah-stress-{index}",
            scenario=scenario,
            regime_digest="wave5ah-regime-digest",
            initial_state_digest=f"wave5ah-initial-{index}",
            final_state_digest=f"wave5ah-final-{index}",
            checkpoint_anchor=f"wave5ah-checkpoint-{index}",
            event_anchor=f"wave5ah-event-{index}",
            plan_revision_before=f"wave5ah-plan-before-{index}",
            plan_revision_after=f"wave5ah-plan-after-{index}",
            contamination_count=0,
            stale_context_count=0,
            false_accepts=0,
            regressions=0,
            recovered=True,
            elapsed_logical_epochs=index,
            evidence=evidence,
        )
        observation_ids.append(row.observation_id)

    assessment = ledger.assess_suite(tuple(observation_ids))
    assert assessment.passed
    assert assessment.missing_scenarios == ()
    assert assessment.reasons == ()

    state = ledger.to_state()
    restored = LongHorizonStressLedger.from_state(registry=registry, state=state)
    assert restored.to_state() == state
    assert restored.get_assessment(assessment.assessment_id) == assessment
    for observation_id in observation_ids:
        assert restored.get_observation(observation_id) == ledger.get_observation(observation_id)


def test_wave5ah_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.stress"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.stress"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.stress")) == "0.0.1"
    assert all(binding.component_id != "evaluation.stress" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.stress" not in ids
    assert len(state["components"]) <= 15


def test_wave5ah_current_status_tracks_native_stress_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AH" in status
    assert "evaluation.stress" in status
    assert "15 non-native" in status
