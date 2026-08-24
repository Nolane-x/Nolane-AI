from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.events import EventLedger
from nolane.organization.identity import AgentRegistry

ROOT = Path(__file__).resolve().parents[1]


def _runtime():
    return AgentRegistry(build_first_generation_blueprint()), EventLedger()


def test_wave5h_experience_is_canonical_native_and_versioned() -> None:
    row = build_component_implementation_ledger()["external.experience"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.experience"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.experience")) == "0.0.1"


def test_wave5h_experience_retires_facade_and_preserves_all_symbol_identities() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert "external.experience" not in facade_ids
    assert "external.self_model" in facade_ids

    import cogcoder.organization.experience as legacy
    import nolane.memory.experience as canonical

    for name in ("ExperienceOutcome", "LearningLayer", "ExperienceRecord", "AttributionRecord", "ExperienceLedger"):
        assert getattr(legacy, name) is getattr(canonical, name)
        assert getattr(canonical, name).__module__ == "nolane.memory.experience"


def test_wave5h_canonical_experience_has_no_historical_owner_reverse_import() -> None:
    import nolane.memory.experience as experience

    source_path = Path(experience.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.experience":
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.experience":
                offenders.append(f"from:{node.lineno}:{module}")
            elif module == "cogcoder.organization" and any(alias.name == "experience" for alias in node.names):
                offenders.append(f"from:{node.lineno}:{module}.experience")
    assert offenders == [], "canonical Experience reverse-imports its historical owner: " + "; ".join(offenders)


def test_wave5h_experience_preserves_record_attribution_and_restore_behavior() -> None:
    from nolane.memory.experience import ExperienceLedger, ExperienceOutcome, LearningLayer

    registry, events = _runtime()
    ledger = ExperienceLedger(registry=registry, events=events)
    agent_id = "coding.backend.01"
    first = ledger.record(
        agent_id=agent_id,
        author_agent_id=agent_id,
        domain="python",
        outcome=ExperienceOutcome.SUCCESS,
        summary="bounded repair",
        task_id="task-1",
        object_refs=("artifact-1",),
        evidence_refs=("evidence-1",),
    )
    assert first.experience_id.startswith("experience-")
    assert ledger.record(
        agent_id=agent_id,
        author_agent_id=agent_id,
        domain="python",
        outcome="success",
        summary="bounded repair",
        task_id="task-1",
        object_refs=("artifact-1",),
        evidence_refs=("evidence-1",),
    ) is first
    with pytest.raises(PermissionError, match="only author their own"):
        ledger.record(agent_id=agent_id, author_agent_id="verification.chief", domain="python", outcome="failure", summary="bad")
    with pytest.raises(ValueError, match="domain and summary"):
        ledger.record(agent_id=agent_id, author_agent_id=agent_id, domain="", outcome="mixed", summary="bad")

    clean = EvidenceRecord("evidence-clean", "verification.chief", True, false_accepts=0, regressions=0)
    positive = ledger.attribute(first.experience_id, learning_layer=LearningLayer.PROCEDURAL, lesson="keep boundary", evidence=clean)
    assert positive.positive
    assert positive.attribution_id.startswith("attribution-")

    self_clean = EvidenceRecord("evidence-self", agent_id, True, false_accepts=0, regressions=0)
    with pytest.raises(PermissionError, match="external to the producer"):
        ledger.attribute(first.experience_id, learning_layer="semantic", lesson="self-certified", evidence=self_clean)

    dirty = EvidenceRecord("evidence-dirty", agent_id, False, false_accepts=1, regressions=1)
    negative = ledger.attribute(first.experience_id, learning_layer="strategy", lesson="avoid failure", evidence=dirty)
    assert not negative.positive

    state = ledger.to_state()
    restored = ExperienceLedger.from_state(registry=registry, events=events, state=state)
    assert restored.to_state() == state
    with pytest.raises(ValueError, match="missing experience"):
        ExperienceLedger.from_state(registry=registry, events=events, state={"experiences": [], "attributions": state["attributions"]})


def test_wave5h_inventory_and_debt_are_exact() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/organization/experience.py").canonical_destination == "nolane/memory/experience.py"

    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1
    assert len(non_native) == 37
    assert counts == {"compatibility_facade": 27, "frozen_asset": 1, "historical_only": 7, "legacy_internal": 2}
    assert ledger["external.self_model"].status is ImplementationStatus.COMPATIBILITY_FACADE
