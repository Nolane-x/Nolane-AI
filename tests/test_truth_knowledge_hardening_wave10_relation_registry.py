from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.memory.knowledge import (
    RelationCardinality,
    RelationSemanticsRegistry,
    RelationSemanticsRevision,
)


def revision(
    relation: str,
    number: int,
    cardinality: RelationCardinality,
    *,
    previous_digest: str = "",
) -> RelationSemanticsRevision:
    return RelationSemanticsRevision.create(
        relation=relation,
        revision=number,
        cardinality=cardinality,
        previous_digest=previous_digest,
    )


def test_a10_registry_defaults_to_unspecified_and_records_first_revision():
    registry = RelationSemanticsRegistry()
    assert registry.cardinality("speaks") is RelationCardinality.UNSPECIFIED

    row = revision("status", 1, RelationCardinality.EXCLUSIVE)
    assert registry.record(row) == row
    assert registry.current("status") == row
    assert registry.cardinality("status") is RelationCardinality.EXCLUSIVE
    assert registry.revisions("status") == (row,)


def test_a10_registry_revision_chain_is_monotonic_and_predecessor_bound():
    registry = RelationSemanticsRegistry()
    first = registry.record(revision("status", 1, RelationCardinality.EXCLUSIVE))
    second = registry.record(revision(
        "status",
        2,
        RelationCardinality.MULTI_VALUED,
        previous_digest=first.digest,
    ))
    assert registry.current("status") == second
    assert registry.revisions("status") == (first, second)

    with pytest.raises(ValueError, match="revision sequence"):
        registry.record(revision(
            "status",
            4,
            RelationCardinality.EXCLUSIVE,
            previous_digest=second.digest,
        ))

    with pytest.raises(ValueError, match="predecessor"):
        registry.record(revision(
            "status",
            3,
            RelationCardinality.EXCLUSIVE,
            previous_digest=first.digest,
        ))

    with pytest.raises(ValueError, match="revision sequence"):
        registry.record(revision(
            "status",
            1,
            RelationCardinality.EXCLUSIVE,
        ))


def test_a10_same_relation_revision_cannot_rebind_semantics():
    registry = RelationSemanticsRegistry()
    first = registry.record(revision("status", 1, RelationCardinality.EXCLUSIVE))
    assert registry.record(first) == first

    rebound = revision("status", 1, RelationCardinality.MULTI_VALUED)
    with pytest.raises(ValueError, match="revision collision"):
        registry.record(rebound)


def test_a10_projection_digest_changes_only_for_relevant_relation_policy():
    registry = RelationSemanticsRegistry()
    initial = registry.projection_digest(("status",))

    speaks = registry.record(revision("speaks", 1, RelationCardinality.MULTI_VALUED))
    assert registry.projection_digest(("status",)) == initial

    status = registry.record(revision("status", 1, RelationCardinality.EXCLUSIVE))
    relevant = registry.projection_digest(("status",))
    assert relevant != initial

    registry.record(revision(
        "speaks",
        2,
        RelationCardinality.EXCLUSIVE,
        previous_digest=speaks.digest,
    ))
    assert registry.projection_digest(("status",)) == relevant

    registry.record(revision(
        "status",
        2,
        RelationCardinality.MULTI_VALUED,
        previous_digest=status.digest,
    ))
    assert registry.projection_digest(("status",)) != relevant


def test_a10_projection_explicitly_represents_unspecified_relations():
    registry = RelationSemanticsRegistry()
    state = registry.projection_state(("speaks", "status"))
    assert state["relations"] == [
        {"relation": "speaks", "status": "unspecified"},
        {"relation": "status", "status": "unspecified"},
    ]

    registry.record(revision("speaks", 1, RelationCardinality.MULTI_VALUED))
    state = registry.projection_state(("speaks", "status"))
    assert state["relations"][0]["relation"] == "speaks"
    assert state["relations"][0]["status"] == "registered"
    assert state["relations"][0]["revision"]["cardinality"] == "multi_valued"
    assert state["relations"][1] == {"relation": "status", "status": "unspecified"}


def test_a10_registry_roundtrip_rejects_duplicate_and_tampered_revision_state():
    registry = RelationSemanticsRegistry()
    first = registry.record(revision("status", 1, RelationCardinality.EXCLUSIVE))
    registry.record(revision(
        "status",
        2,
        RelationCardinality.MULTI_VALUED,
        previous_digest=first.digest,
    ))
    registry.record(revision("speaks", 1, RelationCardinality.MULTI_VALUED))

    state = registry.to_state()
    restored = RelationSemanticsRegistry.from_state(deepcopy(state))
    assert restored.to_state() == state
    assert restored.digest == registry.digest

    duplicate = deepcopy(state)
    duplicate["revisions"].append(deepcopy(duplicate["revisions"][0]))
    with pytest.raises(ValueError, match="duplicate serialized relation revision"):
        RelationSemanticsRegistry.from_state(duplicate)

    tampered = deepcopy(state)
    status_v1 = next(
        row for row in tampered["revisions"]
        if row["relation"] == "status" and row["revision"] == 1
    )
    status_v1["cardinality"] = RelationCardinality.MULTI_VALUED.value
    with pytest.raises(ValueError, match="relation semantics revision digest mismatch"):
        RelationSemanticsRegistry.from_state(tampered)


def test_a10_revision_identity_requires_explicit_valid_fields():
    with pytest.raises(ValueError):
        revision("", 1, RelationCardinality.EXCLUSIVE)
    with pytest.raises(ValueError):
        revision("status", 0, RelationCardinality.EXCLUSIVE)
    with pytest.raises(ValueError):
        revision("status", 1, RelationCardinality.EXCLUSIVE, previous_digest="unexpected")
