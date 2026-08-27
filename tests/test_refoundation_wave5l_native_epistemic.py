from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT
from cogcoder.knowledge_types import EvidenceChunk


ROOT = Path(__file__).resolve().parents[1]


def _chunk(
    text: str,
    *,
    cid: str,
    source: str,
    version: str,
    trust: float = 0.9,
    score: float = 0.8,
) -> EvidenceChunk:
    return EvidenceChunk(
        cid,
        cid,
        source,
        text,
        hashlib.sha256(text.encode()).hexdigest(),
        version,
        0,
        len(text),
        score,
        score,
        score,
        trust,
    )


def test_wave5l_historical_epistemic_behavior_stays_green_during_cutover() -> None:
    from cogcoder.epistemic_workspace import EpistemicWorkspace

    workspace = EpistemicWorkspace()
    assert workspace.trainable_parameter_count == 0
    assert workspace.ingest(_chunk("alpha --next--> old", cid="old", source="kb://route", version="1", trust=0.99))
    assert workspace.ingest(_chunk("alpha --next--> new", cid="new", source="kb://route", version="2", trust=0.80))
    assert workspace.ingest(_chunk("alpha --next--> beta", cid="b1", source="kb://one", version="3", trust=0.82))
    assert workspace.ingest(_chunk("alpha --next--> beta", cid="b2", source="kb://two", version="1", trust=0.81))
    assert workspace.ingest(_chunk("alpha --next--> gamma", cid="g", source="kb://three", version="4", trust=0.88))

    belief = workspace.belief("alpha", "next")
    assert belief.object == "beta"
    assert belief.independent_sources == 2
    assert "gamma" in belief.alternatives
    assert "old" in belief.superseded_chunk_ids
    assert workspace.conflicts()
    assert workspace.verify_provenance()


def test_wave5l_epistemic_preserves_idempotence_collision_and_tamper_fail_closed() -> None:
    from cogcoder.epistemic_workspace import EpistemicWorkspace

    workspace = EpistemicWorkspace()
    good = _chunk("alpha --next--> beta", cid="a", source="kb://one", version="1")
    assert workspace.ingest(good) is True
    assert workspace.ingest(good) is False

    rebound = _chunk("alpha --next--> gamma", cid="a", source="kb://two", version="1")
    with pytest.raises(ValueError, match="chunk id collision"):
        workspace.ingest(rebound)

    assert workspace.verify_provenance()
    object.__setattr__(good, "text", "alpha --next--> tampered")
    assert workspace.verify_provenance() is False


def test_wave5l_epistemic_preserves_unresolved_and_contested_followup_queries() -> None:
    from cogcoder.epistemic_workspace import EpistemicWorkspace

    workspace = EpistemicWorkspace()
    assert workspace.missing_queries("alpha", "next") == ("alpha next current authoritative",)
    workspace.ingest(_chunk("alpha --next--> beta", cid="a", source="kb://one", version="1", trust=0.8, score=0.8))
    workspace.ingest(_chunk("alpha --next--> gamma", cid="b", source="kb://two", version="1", trust=0.8, score=0.8))
    belief = workspace.belief("alpha", "next")
    assert belief.contested is True
    queries = workspace.missing_queries("alpha", "next")
    assert len(queries) == 1
    assert "alpha next" in queries[0]
    assert "beta" in queries[0] and "gamma" in queries[0]


def test_wave5l_epistemic_is_canonical_native_and_versioned() -> None:
    row = build_component_implementation_ledger()["external.epistemic"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.epistemic"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.epistemic")) == "0.0.1"


def test_wave5l_public_epistemic_objects_bridge_to_canonical_identity() -> None:
    from cogcoder.epistemic_workspace import Belief as LegacyBelief
    from cogcoder.epistemic_workspace import ClaimRecord as LegacyClaimRecord
    from cogcoder.epistemic_workspace import EpistemicConflict as LegacyConflict
    from cogcoder.epistemic_workspace import EpistemicWorkspace as LegacyWorkspace
    from nolane.external_core.epistemic import Belief, ClaimRecord, EpistemicConflict, EpistemicWorkspace

    assert LegacyClaimRecord is ClaimRecord
    assert LegacyBelief is Belief
    assert LegacyConflict is EpistemicConflict
    assert LegacyWorkspace is EpistemicWorkspace
    assert ClaimRecord.__module__ == "nolane.external_core.epistemic"
    assert Belief.__module__ == "nolane.external_core.epistemic"
    assert EpistemicConflict.__module__ == "nolane.external_core.epistemic"
    assert EpistemicWorkspace.__module__ == "nolane.external_core.epistemic"


def test_wave5l_canonical_epistemic_has_no_executable_historical_reverse_imports() -> None:
    import nolane.external_core.epistemic as epistemic

    source_path = Path(epistemic.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder" or alias.name.startswith("cogcoder."):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder" or module.startswith("cogcoder."):
                offenders.append(f"from:{node.lineno}:{module}")
    assert offenders == [], "canonical Epistemic reverse-imports historical authority: " + "; ".join(offenders)


def test_wave5l_inventory_maps_only_dedicated_r22_epistemic_lineage() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/epistemic_workspace.py").canonical_destination == "nolane/external_core/epistemic.py"


def test_wave5l_epistemic_never_regresses_back_into_native_debt() -> None:
    """Protect the Wave 5L cutover without freezing later-wave progress.

    A predecessor wave owns the invariant it established, not the repository's
    forever-changing aggregate debt count.  Later accepted native cutovers must
    be free to reduce debt without rewriting this historical acceptance test.
    """

    ledger = build_component_implementation_ledger()
    non_native_ids = {
        component_id
        for component_id, row in ledger.items()
        if row.status is not ImplementationStatus.CANONICAL_NATIVE
    }

    assert "external.epistemic" not in non_native_ids
    epistemic = ledger["external.epistemic"]
    assert epistemic.status is ImplementationStatus.CANONICAL_NATIVE
    assert epistemic.canonical_module == "nolane.external_core.epistemic"
    assert epistemic.canonical_write_authority
    assert epistemic.component_version == "0.0.1"

    # Wave 5L was stacked after Wave 5K.  A later wave may migrate additional
    # components, but it must never demote already accepted predecessor owners.
    knowledge = ledger["external.knowledge"]
    assert knowledge.status is ImplementationStatus.CANONICAL_NATIVE
    assert knowledge.canonical_write_authority
