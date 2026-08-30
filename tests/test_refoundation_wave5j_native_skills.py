from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT
from nolane.external_core.evidence import EvidenceRecord


ROOT = Path(__file__).resolve().parents[1]


def _evidence(
    verifier: str,
    *,
    passed: bool = True,
    false_accepts: int = 0,
    regressions: int = 0,
    evidence_id: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id or f"evidence-{verifier}-{int(passed)}-{false_accepts}-{regressions}",
        verifier,
        passed,
        false_accepts=false_accepts,
        regressions=regressions,
    )


def test_wave5j_skills_are_canonical_native_and_versioned() -> None:
    row = build_component_implementation_ledger()["external.skills"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.skills"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.2"
    assert str(component_version("external.skills")) == "0.0.2"


def test_wave5j_skills_leave_context_facade_untouched() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert "external.skills" not in facade_ids
    ledger = build_component_implementation_ledger()
    assert ledger["external.skills"].status is ImplementationStatus.CANONICAL_NATIVE


def test_wave5j_skill_objects_and_scope_bridge_to_canonical_identity() -> None:
    from cogcoder.organization.evolution import SkillEvolutionEngine as LegacyEngine
    from cogcoder.organization.evolution import SkillRecord as LegacyRecord
    from cogcoder.organization.evolution import SkillScope as LegacyEvolutionScope
    from cogcoder.organization.types import SkillScope as LegacyTypesScope
    from nolane.memory.skills import SkillEvolutionEngine, SkillRecord, SkillScope

    assert LegacyEngine is SkillEvolutionEngine
    assert LegacyRecord is SkillRecord
    assert LegacyEvolutionScope is SkillScope
    assert LegacyTypesScope is SkillScope
    assert SkillEvolutionEngine.__module__ == "nolane.memory.skills"
    assert SkillRecord.__module__ == "nolane.memory.skills"
    assert SkillScope.__module__ == "nolane.memory.skills"


def test_wave5j_canonical_skills_have_no_executable_historical_reverse_imports() -> None:
    import nolane.memory.skills as skills

    source_path = Path(skills.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    forbidden = {"cogcoder.organization.evolution", "cogcoder.organization.types"}
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden:
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden:
                offenders.append(f"from:{node.lineno}:{module}")
    assert offenders == [], "canonical Skills reverse-import historical authority: " + "; ".join(offenders)


def test_wave5j_skills_preserve_deterministic_proposal_and_validation() -> None:
    from nolane.memory.skills import SkillEvolutionEngine

    engine = SkillEvolutionEngine()
    first = engine.propose(owner_agent_id="agent-a", region="coding", name="repair", body="bounded repair")
    second = engine.propose(owner_agent_id="agent-a", region="coding", name="repair", body="bounded repair")
    assert second is first
    assert first.skill_id == "skill-" + first.content_digest[:20]
    assert first.scope.value == "candidate"

    for kwargs in (
        dict(owner_agent_id="", region="coding", name="repair", body="body"),
        dict(owner_agent_id="agent-a", region="", name="repair", body="body"),
        dict(owner_agent_id="agent-a", region="coding", name="", body="body"),
        dict(owner_agent_id="agent-a", region="coding", name="repair", body=""),
    ):
        with pytest.raises(ValueError, match="must be explicit"):
            engine.propose(**kwargs)


def test_wave5j_skills_preserve_evidence_rebinding_and_promotion_rules() -> None:
    from nolane.memory.skills import SkillEvolutionEngine, SkillScope

    engine = SkillEvolutionEngine()
    skill = engine.propose(owner_agent_id="agent-a", region="coding", name="repair", body="bounded repair")

    with pytest.raises(ValueError, match="candidate is not a promotion target"):
        engine.promote(skill.skill_id, SkillScope.CANDIDATE)

    dirty = _evidence("verifier-dirty", passed=False, regressions=1)
    engine.verify(skill.skill_id, dirty)
    with pytest.raises(PermissionError, match="requires 1 independent valid verifier"):
        engine.promote(skill.skill_id, SkillScope.PERSONAL)

    ev1 = _evidence("verifier-1", evidence_id="evidence-1")
    row = engine.verify(skill.skill_id, ev1)
    assert tuple(e.evidence_id for e in row.evidence) == tuple(sorted(e.evidence_id for e in row.evidence))
    with pytest.raises(ValueError, match="cannot be rebound"):
        engine.verify(skill.skill_id, _evidence("other-verifier", evidence_id="evidence-1"))

    personal = engine.promote(skill.skill_id, SkillScope.PERSONAL)
    assert personal.scope is SkillScope.PERSONAL
    with pytest.raises(PermissionError, match="requires 2 independent valid verifier"):
        engine.promote(skill.skill_id, SkillScope.REGIONAL)

    engine.verify(skill.skill_id, _evidence("verifier-2", evidence_id="evidence-2"))
    regional = engine.promote(skill.skill_id, SkillScope.REGIONAL)
    assert regional.scope is SkillScope.REGIONAL
    with pytest.raises(PermissionError, match="requires 3 independent valid verifier"):
        engine.promote(skill.skill_id, SkillScope.GLOBAL)

    engine.verify(skill.skill_id, _evidence("verifier-3", evidence_id="evidence-3"))
    global_skill = engine.promote(skill.skill_id, SkillScope.GLOBAL)
    assert global_skill.scope is SkillScope.GLOBAL
    with pytest.raises(ValueError, match="cannot silently demote"):
        engine.promote(skill.skill_id, SkillScope.REGIONAL)


def test_wave5j_skills_preserve_quarantine_visibility_and_state_roundtrip() -> None:
    from nolane.memory.skills import SkillEvolutionEngine, SkillScope

    engine = SkillEvolutionEngine()

    personal = engine.propose(owner_agent_id="agent-a", region="r1", name="personal", body="p")
    engine.verify(personal.skill_id, _evidence("v1", evidence_id="p-1"))
    engine.promote(personal.skill_id, SkillScope.PERSONAL)

    regional = engine.propose(owner_agent_id="agent-b", region="r1", name="regional", body="r")
    engine.verify(regional.skill_id, _evidence("v1", evidence_id="r-1"))
    engine.verify(regional.skill_id, _evidence("v2", evidence_id="r-2"))
    engine.promote(regional.skill_id, SkillScope.REGIONAL)

    global_row = engine.propose(owner_agent_id="agent-c", region="r2", name="global", body="g")
    for index in range(1, 4):
        engine.verify(global_row.skill_id, _evidence(f"v{index}", evidence_id=f"g-{index}"))
    engine.promote(global_row.skill_id, SkillScope.GLOBAL)

    candidate = engine.propose(owner_agent_id="agent-a", region="r1", name="candidate", body="c")
    quarantined = engine.propose(owner_agent_id="agent-a", region="r1", name="quarantine", body="q")
    with pytest.raises(ValueError, match="reason must be explicit"):
        engine.quarantine(quarantined.skill_id, reason=" ")
    engine.verify(quarantined.skill_id, _evidence("v9", evidence_id="q-1"))
    engine.quarantine(quarantined.skill_id, reason="regression")
    with pytest.raises(PermissionError, match="quarantined skill cannot be promoted"):
        engine.promote(quarantined.skill_id, SkillScope.PERSONAL)

    visible_a_r1 = {row.skill_id for row in engine.skills_for("agent-a", region="r1")}
    assert visible_a_r1 == {personal.skill_id, regional.skill_id, global_row.skill_id}
    assert candidate.skill_id not in visible_a_r1
    assert quarantined.skill_id not in visible_a_r1

    visible_other_r2 = {row.skill_id for row in engine.skills_for("agent-z", region="r2")}
    assert visible_other_r2 == {global_row.skill_id}

    state = engine.to_state()
    restored = SkillEvolutionEngine.from_state(state)
    assert restored.to_state() == state
    assert restored.get(global_row.skill_id).scope is SkillScope.GLOBAL


def test_wave5j_inventory_preserves_dedicated_skill_destination_without_conflating_types() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/organization/evolution.py").canonical_destination == "nolane/memory/skills.py"
    assert census.get("cogcoder/organization/types.py").canonical_destination != "nolane/memory/skills.py"


def test_wave5j_debt_invariants_are_monotonic_after_skills_cutover() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    # Wave 5J accepted 35 non-native records with 25 compatibility facades,
    # 7 historical-only records, 2 legacy internals and 1 frozen asset. Later
    # native waves may only reduce these buckets; this predecessor contract must
    # not freeze future accepted migrations at the Wave 5J snapshot forever.
    assert len(non_native) <= 35
    assert counts.get("compatibility_facade", 0) <= 25
    assert counts.get("historical_only", 0) <= 7
    assert counts.get("legacy_internal", 0) <= 2
    assert counts.get("frozen_asset", 0) <= 1
    assert ledger["external.skills"].status is ImplementationStatus.CANONICAL_NATIVE
