from __future__ import annotations

from types import SimpleNamespace

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.assurance import AssuranceDisposition
from nolane.external_core.research import (
    CurrentResearchHandoffDisposition,
    ResearchControlPlane,
    ResearchHandoff,
    ResearchHandoffDisposition,
    ResearchSynthesis,
)
from nolane.external_core.research_profiles import ResearchDomain
from nolane.external_core.research_provenance import ClaimDisposition, EvidenceMode


class _CurrentProvenance:
    def __init__(self) -> None:
        self.fresh = True
        self.claim_disposition = ClaimDisposition.SUPPORTED
        self.digest = "provenance-current"

    def is_finding_fresh(self, finding_id: str) -> bool:
        assert finding_id == "finding-1"
        return self.fresh

    def assess_claim(self, claim_key: str):
        assert claim_key == "claim-1"
        return SimpleNamespace(disposition=self.claim_disposition)


class _EvidenceSubjects:
    def __init__(self, artifact_id: str) -> None:
        self.subject = SimpleNamespace(subject_id="subject-1", artifact_id=artifact_id)

    def get_subject(self, subject_id: str):
        if subject_id != self.subject.subject_id:
            raise KeyError(subject_id)
        return self.subject


class _CurrentAssurance:
    def __init__(self, artifact_id: str) -> None:
        self.evidence = _EvidenceSubjects(artifact_id)
        self.disposition = AssuranceDisposition.VERIFIED

    def effective_disposition(self, subject_id: str) -> AssuranceDisposition:
        assert subject_id == "subject-1"
        return self.disposition


def _control_plane_fixture():
    artifacts = ArtifactStore()
    core_payload = {
        "synthesis_id": "synthesis-1",
        "producer_agent_id": "research.chief",
        "title": "Recovery research",
        "finding_ids": ["finding-1"],
        "claim_keys": ["claim-1"],
        "source_ids": ["source-1"],
        "evidence_modes": [EvidenceMode.CURRENT_EXTERNAL.value],
        "domains": [ResearchDomain.DOCS_API.value],
        "conclusion": "candidate appears useful",
        "limitations": ["one platform"],
        "evidence_refs": ["research-evidence-1"],
        "reasons": [],
        "shareable": True,
        "created_epoch": 1,
    }
    artifact = artifacts.put(
        kind="research-synthesis",
        producer_agent_id="research.chief",
        content=canonical_json(core_payload),
        evidence_refs=("research-evidence-1",),
        metadata={
            "synthesis_id": "synthesis-1",
            "shareable": True,
            "source_modes": [EvidenceMode.CURRENT_EXTERNAL.value],
        },
    )
    synthesis_payload = {**core_payload, "artifact_id": artifact.artifact_id}
    synthesis = ResearchSynthesis(
        synthesis_id="synthesis-1",
        producer_agent_id="research.chief",
        title="Recovery research",
        finding_ids=("finding-1",),
        claim_keys=("claim-1",),
        source_ids=("source-1",),
        evidence_modes=(EvidenceMode.CURRENT_EXTERNAL,),
        domains=(ResearchDomain.DOCS_API,),
        conclusion="candidate appears useful",
        limitations=("one platform",),
        evidence_refs=("research-evidence-1",),
        reasons=(),
        shareable=True,
        artifact_id=artifact.artifact_id,
        created_epoch=1,
        digest=canonical_digest(synthesis_payload),
    )
    handoff_payload = {
        "handoff_id": "research-handoff-00000001",
        "synthesis_id": synthesis.synthesis_id,
        "synthesis_artifact_id": synthesis.artifact_id,
        "target_agent_id": "planning.chief",
        "target_region": "planning-program",
        "purpose": "planning-input",
        "authorizing": True,
        "assurance_subject_id": "subject-1",
        "assurance_disposition": AssuranceDisposition.VERIFIED.value,
        "disposition": ResearchHandoffDisposition.AUTHORIZED.value,
        "reasons": [],
        "evidence_refs": ["handoff-evidence-1"],
    }
    handoff = ResearchHandoff(
        handoff_id=handoff_payload["handoff_id"],
        synthesis_id=synthesis.synthesis_id,
        synthesis_artifact_id=synthesis.artifact_id,
        target_agent_id=handoff_payload["target_agent_id"],
        target_region=handoff_payload["target_region"],
        purpose=handoff_payload["purpose"],
        authorizing=True,
        assurance_subject_id="subject-1",
        assurance_disposition=AssuranceDisposition.VERIFIED,
        disposition=ResearchHandoffDisposition.AUTHORIZED,
        reasons=(),
        evidence_refs=("handoff-evidence-1",),
        digest=canonical_digest(handoff_payload),
    )

    plane = ResearchControlPlane.__new__(ResearchControlPlane)
    plane.artifacts = artifacts
    plane.provenance = _CurrentProvenance()
    plane.assurance = _CurrentAssurance(artifact.artifact_id)
    plane._syntheses = {synthesis.synthesis_id: synthesis}
    plane._handoffs = {handoff.handoff_id: handoff}
    return plane, synthesis, handoff


def test_historical_authorized_handoff_is_current_only_after_revalidation():
    plane, _, handoff = _control_plane_fixture()
    result = plane.assess_current_handoff(handoff.handoff_id)
    assert result.disposition is CurrentResearchHandoffDisposition.AUTHORIZED
    assert result.reasons == ()
    assert result.historical_handoff_digest == handoff.digest


def test_stale_research_basis_blocks_historically_authorized_handoff():
    plane, _, handoff = _control_plane_fixture()
    plane.provenance.fresh = False
    result = plane.assess_current_handoff(handoff.handoff_id)
    assert result.disposition is CurrentResearchHandoffDisposition.BLOCKED
    assert "stale_finding" in result.reasons


def test_assurance_rejection_blocks_historically_authorized_handoff():
    plane, _, handoff = _control_plane_fixture()
    plane.assurance.disposition = AssuranceDisposition.REJECTED
    result = plane.assess_current_handoff(handoff.handoff_id)
    assert result.disposition is CurrentResearchHandoffDisposition.BLOCKED
    assert "assurance_not_currently_verified" in result.reasons


def test_pending_assurance_yields_unknown_not_authorized():
    plane, _, handoff = _control_plane_fixture()
    plane.assurance.disposition = AssuranceDisposition.PENDING
    result = plane.assess_current_handoff(handoff.handoff_id)
    assert result.disposition is CurrentResearchHandoffDisposition.UNKNOWN
    assert "assurance_currentness_unresolved" in result.reasons


def test_mutated_legacy_artifact_is_detected_during_current_assessment():
    plane, synthesis, handoff = _control_plane_fixture()
    original = plane.artifacts.get(synthesis.artifact_id)
    plane.artifacts._rows[synthesis.artifact_id] = type(original)(
        artifact_id=original.artifact_id,
        digest=original.digest,
        kind=original.kind,
        producer_agent_id=original.producer_agent_id,
        content="tampered-content",
        evidence_refs=original.evidence_refs,
        metadata_json=original.metadata_json,
    )
    result = plane.assess_current_handoff(handoff.handoff_id)
    assert result.disposition is CurrentResearchHandoffDisposition.BLOCKED
    assert "artifact_integrity_mismatch" in result.reasons
