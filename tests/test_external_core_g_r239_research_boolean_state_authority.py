from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.research import ResearchHandoff, ResearchSynthesis


def test_research_synthesis_restore_requires_exact_boolean_shareable() -> None:
    payload = {
        "synthesis_id": "synthesis-r239",
        "producer_agent_id": "research.chief",
        "title": "R2.39 synthesis",
        "finding_ids": [],
        "claim_keys": [],
        "source_ids": [],
        "evidence_modes": [],
        "domains": [],
        "conclusion": "bounded research synthesis",
        "limitations": [],
        "evidence_refs": [],
        "reasons": [],
        "shareable": True,
        "artifact_id": "artifact-r239",
        "created_epoch": 1,
    }
    state = {**payload, "digest": canonical_digest(payload)}
    state["shareable"] = "false"

    with pytest.raises(ValueError, match="research synthesis shareable must be an exact boolean"):
        ResearchSynthesis.from_state(state)


def test_research_handoff_restore_requires_exact_boolean_authorizing() -> None:
    payload = {
        "handoff_id": "research-handoff-r239",
        "synthesis_id": "synthesis-r239",
        "synthesis_artifact_id": "artifact-r239",
        "target_agent_id": "architecture.chief",
        "target_region": "architecture-system",
        "purpose": "bounded research handoff",
        "authorizing": True,
        "assurance_subject_id": None,
        "assurance_disposition": None,
        "disposition": "authorized",
        "reasons": [],
        "evidence_refs": [],
    }
    state = {**payload, "digest": canonical_digest(payload)}
    state["authorizing"] = "false"

    with pytest.raises(ValueError, match="research handoff authorizing must be an exact boolean"):
        ResearchHandoff.from_state(state)
