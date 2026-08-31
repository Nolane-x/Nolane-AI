from __future__ import annotations

import pytest

from nolane.external_core.evidence_dependence_truth import (
    PROJECTION_PROTOCOL,
    TRUTH_PROTOCOL,
    SourceDependenceRegistry,
    SourceDependenceRevision,
)


def _rev(
    source_id: str,
    *,
    revision: int = 1,
    predecessor_digest: str = "",
    basis_ids: tuple[str, ...] = ("basis:measurement",),
) -> SourceDependenceRevision:
    return SourceDependenceRevision.create(
        source_id=source_id,
        revision=revision,
        predecessor_digest=predecessor_digest,
        basis_ids=basis_ids,
    )


def test_a14_dependence_revision_requires_explicit_nonempty_basis():
    with pytest.raises(ValueError, match="basis"):
        _rev("source-a", basis_ids=())
    with pytest.raises(ValueError, match="unique"):
        _rev("source-a", basis_ids=("basis:x", "basis:x"))


def test_a14_dependence_registry_enforces_strict_predecessor_chain():
    registry = SourceDependenceRegistry()
    first = registry.register(_rev("source-a", basis_ids=("basis:a",)))

    with pytest.raises(ValueError, match="advance exactly once"):
        registry.register(
            _rev(
                "source-a",
                revision=3,
                predecessor_digest=first.digest,
                basis_ids=("basis:b",),
            )
        )
    with pytest.raises(ValueError, match="predecessor"):
        registry.register(
            _rev(
                "source-a",
                revision=2,
                predecessor_digest="wrong",
                basis_ids=("basis:b",),
            )
        )

    second = registry.register(
        _rev(
            "source-a",
            revision=2,
            predecessor_digest=first.digest,
            basis_ids=("basis:b",),
        )
    )
    assert registry.current("source-a") == second
    assert registry.basis_ids("source-a") == ("basis:b",)


def test_a14_dependence_projection_is_relevant_only_and_missing_is_explicit():
    registry = SourceDependenceRegistry()
    a1 = registry.register(_rev("source-a", basis_ids=("basis:a",)))
    b1 = registry.register(_rev("source-b", basis_ids=("basis:b",)))

    before = registry.projection_digest(("source-a", "missing-source"))
    state = registry.projection_state(("source-a", "missing-source"))
    assert state["protocol"] == PROJECTION_PROTOCOL
    assert state["requested_source_ids"] == ["missing-source", "source-a"]
    assert any(row == {"source_id": "missing-source", "status": "missing"} for row in state["sources"])

    registry.register(
        _rev(
            "source-b",
            revision=2,
            predecessor_digest=b1.digest,
            basis_ids=("basis:b2",),
        )
    )
    assert registry.projection_digest(("source-a", "missing-source")) == before

    registry.register(
        _rev(
            "source-a",
            revision=2,
            predecessor_digest=a1.digest,
            basis_ids=("basis:a2",),
        )
    )
    assert registry.projection_digest(("source-a", "missing-source")) != before


def test_a14_dependence_restore_rejects_protocol_duplicate_and_sequence_attacks():
    registry = SourceDependenceRegistry()
    first = registry.register(_rev("source-a", basis_ids=("basis:a",)))
    second = registry.register(
        _rev(
            "source-a",
            revision=2,
            predecessor_digest=first.digest,
            basis_ids=("basis:b",),
        )
    )
    state = registry.to_state()
    restored = SourceDependenceRegistry.from_state(state)
    assert restored.to_state() == state
    assert state["protocol"] == TRUTH_PROTOCOL

    wrong_protocol = dict(state)
    wrong_protocol["protocol"] = "wrong"
    with pytest.raises(ValueError, match="protocol"):
        SourceDependenceRegistry.from_state(wrong_protocol)

    duplicate = {"protocol": TRUTH_PROTOCOL, "revisions": [first.to_state(), first.to_state()]}
    with pytest.raises(ValueError, match="duplicate"):
        SourceDependenceRegistry.from_state(duplicate)

    gap = {
        "protocol": TRUTH_PROTOCOL,
        "revisions": [
            first.to_state(),
            SourceDependenceRevision.create(
                source_id="source-a",
                revision=3,
                predecessor_digest=second.digest,
                basis_ids=("basis:c",),
            ).to_state(),
        ],
    }
    with pytest.raises(ValueError, match="ordering|sequence"):
        SourceDependenceRegistry.from_state(gap)

    bad_predecessor = {
        "protocol": TRUTH_PROTOCOL,
        "revisions": [
            first.to_state(),
            SourceDependenceRevision.create(
                source_id="source-a",
                revision=2,
                predecessor_digest="not-first",
                basis_ids=("basis:c",),
            ).to_state(),
        ],
    }
    with pytest.raises(ValueError, match="predecessor"):
        SourceDependenceRegistry.from_state(bad_predecessor)
