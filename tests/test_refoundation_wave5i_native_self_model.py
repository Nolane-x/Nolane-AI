from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


ROOT = Path(__file__).resolve().parents[1]


class _RegistryStub:
    def __init__(self) -> None:
        self._rows = {
            "producer": SimpleNamespace(agent_id="producer", self_model_version="self-model-0.1"),
            "verifier": SimpleNamespace(agent_id="verifier", self_model_version="self-model-0.1"),
        }
        self.updated: dict[str, str] = {}

    def identities(self):
        return tuple(self._rows[key] for key in sorted(self._rows))

    def get(self, agent_id: str):
        try:
            return self._rows[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f"unknown identity: {agent_id}") from exc

    def set_self_model_version(self, agent_id: str, version: str) -> None:
        self.get(agent_id)
        self.updated[str(agent_id)] = str(version)


def _evidence(
    *,
    verifier: str = "verifier",
    passed: bool = True,
    false_accepts: int = 0,
    regressions: int = 0,
):
    from nolane.external_core.evidence import EvidenceRecord

    return EvidenceRecord(
        evidence_id=f"evidence-{verifier}-{int(passed)}-{false_accepts}-{regressions}",
        verifier_agent_id=verifier,
        passed=passed,
        false_accepts=false_accepts,
        regressions=regressions,
        notes="self-model verification",
    )


def test_wave5i_self_model_is_canonical_native_and_versioned() -> None:
    row = build_component_implementation_ledger()["external.self_model"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.self_model"
    assert row.canonical_write_authority is True
    assert row.component_version == "0.0.3"
    assert str(component_version("external.self_model")) == "0.0.3"


def test_wave5i_self_model_and_accepted_downstream_cutovers_stay_out_of_facades() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert "external.self_model" not in facade_ids
    assert "external.individual_evolution" not in facade_ids


def test_wave5i_historical_self_model_objects_bridge_to_canonical_identity() -> None:
    from cogcoder.organization.self_model import SelfModel as LegacySelfModel
    from cogcoder.organization.self_model import SelfModelRegistry as LegacyRegistry
    from nolane.external_core.self_model import SelfModel, SelfModelRegistry

    assert LegacySelfModel is SelfModel
    assert LegacyRegistry is SelfModelRegistry
    assert SelfModel.__module__ == "nolane.external_core.self_model"
    assert SelfModelRegistry.__module__ == "nolane.external_core.self_model"


def test_wave5i_canonical_self_model_has_no_executable_historical_reverse_imports() -> None:
    import nolane.external_core.self_model as self_model

    source_path = Path(self_model.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    forbidden = {
        "cogcoder.organization.self_model",
        "cogcoder.organization.registry",
        "cogcoder.organization.types",
    }
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
    assert offenders == [], "canonical Self-model reverse-imports historical authority: " + "; ".join(offenders)


def test_wave5i_self_model_preserves_initialization_updates_and_state() -> None:
    from nolane.external_core.self_model import SelfModel, SelfModelRegistry

    registry = _RegistryStub()
    models = SelfModelRegistry(registry)
    initial = models.get("producer")
    assert initial == SelfModel("producer", "self-model-0.1")
    assert SelfModel.from_state(initial.to_state()) == initial

    evidence = _evidence()
    updated = models.update_competence(
        "producer",
        domain="reasoning",
        score=0.8,
        evidence=evidence,
    )
    assert updated.version == "self-model-00000002"
    assert updated.domain_competence == (("reasoning", 0.8),)
    assert updated.evidence_ids == (evidence.evidence_id,)
    assert registry.updated == {"producer": "self-model-00000002"}

    second = models.update_competence(
        "producer",
        domain="coding",
        score=0.6,
        evidence=evidence,
    )
    assert second.version == "self-model-00000003"
    assert second.domain_competence == (("coding", 0.6), ("reasoning", 0.8))
    assert second.evidence_ids == (evidence.evidence_id,)

    state = models.to_state()
    restored_registry = _RegistryStub()
    restored = SelfModelRegistry.from_state(restored_registry, state)
    assert restored.to_state() == state
    assert restored.get("producer") == second
    assert restored_registry.updated == {
        "producer": "self-model-00000003",
        "verifier": "self-model-0.1",
    }

    partial_state = {
        "models": [second.to_state()],
        "revisions": {"producer": 3},
    }
    filled = SelfModelRegistry.from_state(_RegistryStub(), partial_state)
    assert filled.get("producer") == second
    assert filled.get("verifier") == SelfModel("verifier", "self-model-0.1")
    assert filled.to_state()["revisions"]["verifier"] == 1


def test_wave5i_self_model_preserves_fail_closed_evidence_and_validation_rules() -> None:
    from nolane.external_core.self_model import SelfModelRegistry

    models = SelfModelRegistry(_RegistryStub())
    with pytest.raises(PermissionError, match="external to the producer"):
        models.update_competence(
            "producer",
            domain="reasoning",
            score=0.5,
            evidence=_evidence(verifier="producer"),
        )
    with pytest.raises(PermissionError, match="without regressions or false accepts"):
        models.update_competence(
            "producer",
            domain="reasoning",
            score=0.5,
            evidence=_evidence(regressions=1),
        )
    with pytest.raises(PermissionError, match="without regressions or false accepts"):
        models.update_competence(
            "producer",
            domain="reasoning",
            score=0.5,
            evidence=_evidence(false_accepts=1),
        )
    with pytest.raises(PermissionError, match="without regressions or false accepts"):
        models.update_competence(
            "producer",
            domain="reasoning",
            score=0.5,
            evidence=_evidence(passed=False),
        )
    with pytest.raises(ValueError, match=r"competence score must lie in \[0, 1\]"):
        models.update_competence(
            "producer",
            domain="reasoning",
            score=1.1,
            evidence=_evidence(),
        )
    with pytest.raises(ValueError, match="competence domain must be explicit"):
        models.update_competence(
            "producer",
            domain=" ",
            score=0.5,
            evidence=_evidence(),
        )
    with pytest.raises(KeyError):
        models.get("missing")


def test_wave5i_inventory_preserves_self_model_canonical_destination() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert (
        census.get("cogcoder/organization/self_model.py").canonical_destination
        == "nolane/external_core/self_model.py"
    )


def test_wave5i_debt_reduces_only_self_model_facade() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    # Wave 5I established an upper bound, not permanent downstream debt.
    assert len(non_native) <= 36
    assert counts.get("compatibility_facade", 0) <= 26
    assert counts.get("frozen_asset", 0) <= 1
    assert counts.get("historical_only", 0) <= 7
    assert counts.get("legacy_internal", 0) <= 2
    assert ledger["external.self_model"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["external.individual_evolution"].status is ImplementationStatus.CANONICAL_NATIVE
