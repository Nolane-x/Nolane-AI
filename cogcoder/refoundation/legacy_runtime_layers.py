from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LegacyRuntimeDisposition(str, Enum):
    COMPATIBILITY = "compatibility"


@dataclass(frozen=True, slots=True)
class LegacyRuntimeLayer:
    legacy_path: str
    semantic_components: tuple[str, ...]
    replacement_modules: tuple[str, ...]
    disposition: LegacyRuntimeDisposition = LegacyRuntimeDisposition.COMPATIBILITY
    canonical_source: bool = False
    delete_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.legacy_path.startswith("cogcoder/organization/runtime"):
            raise ValueError("legacy runtime layer must belong to historical runtime chain")
        if not self.semantic_components or not self.replacement_modules:
            raise ValueError("legacy runtime layer requires semantic replacement coverage")
        if self.canonical_source or self.delete_allowed:
            raise ValueError("Epoch-0 legacy runtime layer cannot be canonical or deletable")


def build_legacy_runtime_layer_map() -> tuple[LegacyRuntimeLayer, ...]:
    return (
        LegacyRuntimeLayer(
            "cogcoder/organization/runtime_core.py",
            (
                "organization.identity", "organization.authority", "organization.events",
                "organization.tasks", "organization.lifecycle", "organization.central",
                "external.memory.fabric", "external.skills", "external.verification",
                "external.artifacts", "external.invokable_cores", "external.self_model",
                "external.requirements", "external.planning", "external.architecture",
                "external.integration", "external.coding.control", "external.debugging",
                "external.ui_ux", "external.assurance", "external.individual_evolution",
                "external.operations", "external.research", "external.context",
            ),
            (
                "nolane.organization.manifests", "nolane.organization.authority",
                "nolane.organization.events", "nolane.organization.tasks",
                "nolane.organization.lifecycle", "nolane.organization.central",
                "nolane.memory.fabric", "nolane.memory.skills", "nolane.external_core.verification",
                "nolane.external_core.artifacts", "nolane.external_core.invokable",
                "nolane.external_core.self_model", "nolane.external_core.requirements",
                "nolane.external_core.planning", "nolane.external_core.architecture",
                "nolane.external_core.integration", "nolane.external_core.coding",
                "nolane.external_core.debugging", "nolane.external_core.ui_ux",
                "nolane.external_core.assurance", "nolane.external_core.individual_evolution",
                "nolane.external_core.operations", "nolane.external_core.research",
                "nolane.memory.context", "nolane.runtime",
            ),
        ),
        LegacyRuntimeLayer(
            "cogcoder/organization/runtime_part13.py",
            ("organization.coordination",),
            ("nolane.organization.coordination", "nolane.runtime"),
        ),
        LegacyRuntimeLayer(
            "cogcoder/organization/runtime_part14.py",
            ("organization.temporary_work_units",),
            ("nolane.work_units", "nolane.runtime"),
        ),
        LegacyRuntimeLayer(
            "cogcoder/organization/runtime_part15.py",
            ("evaluation.scaling",),
            ("nolane.evaluation.scaling", "nolane.runtime"),
        ),
        LegacyRuntimeLayer(
            "cogcoder/organization/runtime.py",
            ("evaluation.campaign", "external.execution.control"),
            ("nolane.evaluation.campaign", "nolane.external_core.execution", "nolane.runtime"),
        ),
    )
