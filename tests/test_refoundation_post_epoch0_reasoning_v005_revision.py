from __future__ import annotations

from cogcoder.refoundation.component_versions import component_revision_map
from nolane.external_core import reasoning_episode
from nolane.external_core import reasoning_evaluation
from nolane.external_core import reasoning_frontier
from nolane.external_core import reasoning_invention
from nolane.external_core import reasoning_meta_learning
from nolane.external_core import reasoning_metacontrol
from nolane.external_core import reasoning_policy_evolution
from nolane.external_core import reasoning_policy_qualification
from nolane.external_core import reasoning_review


def test_reasoning_invention_family_is_coherent_at_v005() -> None:
    modules = (
        reasoning_invention,
        reasoning_evaluation,
        reasoning_frontier,
        reasoning_metacontrol,
        reasoning_review,
        reasoning_meta_learning,
        reasoning_episode,
        reasoning_policy_evolution,
        reasoning_policy_qualification,
    )
    assert {module.COMPONENT_ID for module in modules} == {"external.reasoning_invention"}
    assert {module.COMPONENT_VERSION for module in modules} == {"0.0.5"}
    assert component_revision_map()["external.reasoning_invention"] == 5


def test_c11_adds_schema_without_rewriting_accepted_wire_schemas() -> None:
    assert reasoning_invention.SCHEMA_VERSION == "reasoning-invention-v1"
    assert reasoning_episode.SCHEMA_VERSION == "reasoning-episode-v1"
    assert reasoning_policy_evolution.SCHEMA_VERSION == "reasoning-policy-evolution-v1"
    assert reasoning_policy_qualification.SCHEMA_VERSION == "reasoning-policy-qualification-v1"
