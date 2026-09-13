from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from nolane.organization.authority import AuthorityGraph
from nolane.organization.identity import AgentRegistry


def test_restore_rejects_forward_bound_stale_override_frontier() -> None:
    registry = AgentRegistry(build_first_generation_blueprint())
    graph = AuthorityGraph(registry)
    graph.claim_owner("artifact-r2171-forward", "coding.chief")
    first = graph.record_block(
        "artifact-r2171-forward",
        "verification.chief",
        reason="first independent block",
    )
    stale = graph.central_override(
        artifact_id="artifact-r2171-forward",
        reason="evidence-backed intervention before later block",
        evidence_ids=("EV-R2171-FORWARD-A",),
    )
    second = graph.record_block(
        "artifact-r2171-forward",
        "verification.chief",
        reason="later independent block",
    )

    assert not graph.can_write(
        "nolane.central",
        "artifact-r2171-forward",
        override_id=stale.override_id,
    )

    forged = deepcopy(graph.to_state())
    forged["overrides"][stale.override_id]["block_frontier_ids"] = [
        first.block_id,
        second.block_id,
    ]

    with pytest.raises(ValueError, match="frontier"):
        AuthorityGraph.from_state(registry, forged)
