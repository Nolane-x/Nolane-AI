from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.campaign_contamination import (
    ContaminationFinding,
    ContaminationKind,
)


_BOOL_ALIASES = (0, 0.0, 1, 1.0, "", "false", "true")


def _finding(*, quarantined: object, kinds: tuple[ContaminationKind, ...] = ()) -> ContaminationFinding:
    return ContaminationFinding(
        finding_id="campaign-contamination-r247",
        campaign_id="campaign-r247",
        task_ids=(),
        training_refs=(),
        distillation_refs=(),
        personal_skill_refs=(),
        kinds=kinds,
        quarantined=quarantined,
        digest="digest-r247",
    )


def _canonical_state(
    *,
    quarantined: bool,
    kinds: tuple[ContaminationKind, ...],
) -> dict[str, object]:
    row = _finding(quarantined=quarantined, kinds=kinds)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("alias", _BOOL_ALIASES)
def test_contamination_finding_constructor_rejects_non_bool_quarantined_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="quarantined.*exact bool"):
        _finding(quarantined=alias)


@pytest.mark.parametrize("alias", (0, 0.0))
def test_contamination_finding_restore_rejects_digest_preserving_false_aliases(alias: object) -> None:
    state = _canonical_state(quarantined=False, kinds=())
    state["quarantined"] = alias

    with pytest.raises(ValueError, match="quarantined.*exact bool"):
        ContaminationFinding.from_state(state)


@pytest.mark.parametrize("alias", (1, 1.0))
def test_contamination_finding_restore_rejects_digest_preserving_true_aliases(alias: object) -> None:
    state = _canonical_state(
        quarantined=True,
        kinds=(ContaminationKind.HELDOUT_TASK_REF,),
    )
    state["quarantined"] = alias

    with pytest.raises(ValueError, match="quarantined.*exact bool"):
        ContaminationFinding.from_state(state)


@pytest.mark.parametrize(
    ("quarantined", "kinds"),
    (
        (False, ()),
        (True, (ContaminationKind.HELDOUT_TASK_REF,)),
    ),
)
def test_contamination_finding_preserves_canonical_bool_round_trip(
    quarantined: bool,
    kinds: tuple[ContaminationKind, ...],
) -> None:
    state = _canonical_state(quarantined=quarantined, kinds=kinds)
    restored = ContaminationFinding.from_state(state)

    assert restored.to_state() == state
    assert type(restored.quarantined) is bool
