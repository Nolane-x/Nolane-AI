from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.refoundation.runtime_state_map import (
    RuntimeStateMapper,
    build_runtime_state_bindings,
)


def test_every_current_runtime_top_level_state_section_has_exactly_one_binding() -> None:
    runtime = OrganizationRuntime.first_generation()
    state = runtime.to_state()
    bindings = build_runtime_state_bindings()

    assert {row.legacy_section for row in bindings} == set(state)
    assert len({row.legacy_section for row in bindings}) == len(bindings)


def test_runtime_state_mapping_preserves_every_legacy_section_byte_semantically() -> None:
    runtime = OrganizationRuntime.first_generation()
    state = runtime.to_state()
    envelope = RuntimeStateMapper().map_state(state)

    assert envelope.legacy_section_count == len(state)
    assert envelope.mapped_section_count == len(state)
    assert envelope.unmapped_sections == ()
    assert envelope.lossless
    for binding in build_runtime_state_bindings():
        projected = envelope.section(binding.legacy_section)
        assert projected["legacy_state"] == state[binding.legacy_section]
        assert projected["canonical_owner"] == binding.canonical_owner


def test_governed_learning_validation_state_stays_inside_skill_authority() -> None:
    state = OrganizationRuntime.first_generation().to_state()
    envelope = RuntimeStateMapper().map_state(state)
    learning = envelope.section("learning_substrate")

    assert learning["canonical_owner"] == "external.skills"
    assert learning["legacy_semantics"] is False
    assert learning["legacy_state"] == state["learning_substrate"]


def test_unknown_runtime_state_section_fails_closed() -> None:
    state = OrganizationRuntime.first_generation().to_state()
    state["future_unknown_component"] = {"important": "must not disappear"}

    with pytest.raises(ValueError, match="unmapped runtime state sections"):
        RuntimeStateMapper().map_state(state)


def test_foundry_state_is_preserved_but_owned_by_temporary_work_unit_boundary() -> None:
    state = OrganizationRuntime.first_generation().to_state()
    envelope = RuntimeStateMapper().map_state(state)
    foundry = envelope.section("foundry")

    assert foundry["canonical_owner"] == "organization.temporary_work_units"
    assert foundry["legacy_semantics"] is True
    assert foundry["legacy_state"] == state["foundry"]


def test_part15_evaluation_and_campaign_remain_separate_state_owners() -> None:
    state = OrganizationRuntime.first_generation().to_state()
    envelope = RuntimeStateMapper().map_state(state)

    assert envelope.section("evaluation_scaling")["canonical_owner"] == "evaluation.scaling"
    assert envelope.section("evaluation_campaign")["canonical_owner"] == "evaluation.campaign"
    assert envelope.section("evaluation_scaling")["legacy_state"] == state["evaluation_scaling"]
    assert envelope.section("evaluation_campaign")["legacy_state"] == state["evaluation_campaign"]


def test_runtime_state_envelope_is_digest_bound_and_deterministic() -> None:
    state = OrganizationRuntime.first_generation().to_state()
    first = RuntimeStateMapper().map_state(state)
    second = RuntimeStateMapper().map_state(state)
    assert first.digest == second.digest
    assert len(first.digest) == 64
    assert len(first.legacy_state_digest) == 64