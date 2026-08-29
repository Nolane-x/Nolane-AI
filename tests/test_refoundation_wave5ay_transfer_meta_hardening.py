from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.experience import (
    AttributionRecord,
    ExperienceLedger,
    ExperienceOutcome,
    ExperienceRecord,
    LearningLayer,
)
from nolane.external_core.transfer_meta import TransferMetaGovernor


def _ledger() -> tuple[ExperienceLedger, ExperienceRecord, AttributionRecord]:
    evidence = EvidenceRecord("wave5ay-hardening-evidence", "verification.chief", True)
    source = ExperienceRecord(
        experience_id="wave5ay-hardening-experience",
        agent_id="source.agent",
        region="source-region",
        domain="repository-repair",
        outcome=ExperienceOutcome.SUCCESS,
        summary="original exact source state",
        task_id="task-source",
        object_refs=("object-source",),
        evidence_refs=(evidence.evidence_id,),
    )
    attribution = AttributionRecord(
        attribution_id="wave5ay-hardening-attribution",
        experience_id=source.experience_id,
        agent_id=source.agent_id,
        learning_layer=LearningLayer.STRATEGY,
        lesson="Use the verified portable strategy.",
        positive=True,
        verifier_agent_id=evidence.verifier_agent_id,
        evidence=evidence,
    )
    ledger = object.__new__(ExperienceLedger)
    ledger._experiences = {source.experience_id: source}
    ledger._attributions = {attribution.attribution_id: attribution}
    return ledger, source, attribution


def test_wave5ay_restore_rejects_same_id_source_state_rebinding() -> None:
    ledger, source, attribution = _ledger()
    governor = TransferMetaGovernor(experience=ledger)
    governor.compile_portable(source.experience_id, attribution.attribution_id)
    state = governor.to_state()

    # Simulate a corrupted/rebound native ledger retaining the same public IDs.
    ledger._experiences[source.experience_id] = replace(
        source,
        summary="tampered source state under the same experience id",
    )

    with pytest.raises(ValueError, match="source authority|native source"):
        TransferMetaGovernor.from_state(state, experience=ledger)
