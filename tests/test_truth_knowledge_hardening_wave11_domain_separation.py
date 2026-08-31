from __future__ import annotations

import pytest

from nolane.external_core.evidence_provenance_truth import (
    SourceProvenanceRegistry,
    SourceProvenanceRevision,
    TRUTH_PROTOCOL,
)


def test_a11_source_provenance_revision_state_is_protocol_domain_separated():
    row = SourceProvenanceRevision.create(
        source_id="source-a",
        revision=1,
        controller_id="controller-a",
    )

    state = row.to_state()
    assert state["protocol"] == TRUTH_PROTOCOL
    assert SourceProvenanceRevision.from_state(state) == row

    forged = dict(state)
    forged["protocol"] = "truth-source-provenance-other-domain"
    with pytest.raises(ValueError, match="unsupported source provenance revision protocol"):
        SourceProvenanceRevision.from_state(forged)


def test_a11_relevant_ancestor_revision_stales_descendant_projection():
    registry = SourceProvenanceRegistry()
    parent = registry.register(
        SourceProvenanceRevision.create(
            source_id="root-source",
            revision=1,
            controller_id="root-controller",
        )
    )
    registry.register(
        SourceProvenanceRevision.create(
            source_id="mirror-source",
            revision=1,
            controller_id="root-controller",
            parent_source_ids=("root-source",),
        )
    )
    before = registry.projection_digest(("mirror-source",))

    registry.register(
        SourceProvenanceRevision.create(
            source_id="root-source",
            revision=2,
            predecessor_digest=parent.digest,
            controller_id="root-controller",
        )
    )

    assert registry.projection_digest(("mirror-source",)) != before
