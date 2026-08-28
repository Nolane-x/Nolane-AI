from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable

from nolane.core.canonical_digest import canonical_digest

from .cognitive_catalog import OperatorFamilyDescriptor, SubOperatorDescriptor, build_default_externalization_catalog
from .cognitive_operators import Binary, Const, Expr, Field, IfElse, Unary
from .cognitive_vocabulary import (
    AbstractionCall,
    CognitiveVocabulary,
    LearnedAbstraction,
    TemplateParam,
)


COMPONENT_ID = "external.cognitive_library"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder R2.53/R2.56/R2.57 cognitive-library lineage"


def _expr_from_data(value: Mapping[str, Any]) -> Expr:
    data = dict(value)
    if set(data) == {"field"}:
        return Field(str(data["field"]))
    if set(data) == {"const"}:
        return Const(data["const"])
    if set(data) == {"param"}:
        return TemplateParam(int(data["param"]))
    if set(data) == {"call", "args"}:
        return AbstractionCall(
            str(data["call"]),
            tuple(_expr_from_data(row) for row in data["args"]),
        )
    op = str(data.get("op", ""))
    if op == "if" and set(data) == {"op", "condition", "then", "else"}:
        return IfElse(
            _expr_from_data(data["condition"]),
            _expr_from_data(data["then"]),
            _expr_from_data(data["else"]),
        )
    if set(data) == {"op", "arg"}:
        return Unary(op, _expr_from_data(data["arg"]))
    if set(data) == {"op", "left", "right"}:
        return Binary(op, _expr_from_data(data["left"]), _expr_from_data(data["right"]))
    raise ValueError("invalid cognitive expression state")


def _suboperator_state(row: SubOperatorDescriptor) -> dict[str, Any]:
    return {
        "operator_id": row.operator_id,
        "status": row.status,
        "summary": row.summary,
        "tags": sorted(row.tags),
    }


def _family_state(row: OperatorFamilyDescriptor) -> dict[str, Any]:
    return {
        "family_id": row.family_id,
        "summary": row.summary,
        "suboperators": [_suboperator_state(item) for item in row.suboperators],
    }


def _abstraction_state(row: LearnedAbstraction) -> dict[str, Any]:
    return {
        "abstraction_id": row.abstraction_id,
        "parameter_count": row.parameter_count,
        "template": row.template.to_data(),
        "support_task_ids": list(row.support_task_ids),
        "raw_occurrence_cost": row.raw_occurrence_cost,
        "rewritten_cost": row.rewritten_cost,
    }


class CognitiveLibrary:
    """Canonical deterministic registry for reusable zero-parameter cognition.

    The library owns operator-family descriptions and learned typed abstractions.
    Promotion/quarantine policy, causal programs, active experiments and meta-transfer
    deliberately remain outside this component boundary.
    """

    def __init__(
        self,
        *,
        families: Iterable[OperatorFamilyDescriptor] = (),
        abstractions: Iterable[LearnedAbstraction] = (),
    ) -> None:
        self._families: dict[str, OperatorFamilyDescriptor] = {}
        self._vocabulary = CognitiveVocabulary()
        for family in families:
            self.register_family(family)
        for abstraction in abstractions:
            self.register_abstraction(abstraction)

    @classmethod
    def with_defaults(cls) -> "CognitiveLibrary":
        return cls(families=build_default_externalization_catalog())

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @property
    def vocabulary(self) -> CognitiveVocabulary:
        return self._vocabulary

    def register_family(self, family: OperatorFamilyDescriptor) -> None:
        if not isinstance(family, OperatorFamilyDescriptor):
            raise TypeError("family must be OperatorFamilyDescriptor")
        existing = self._families.get(family.family_id)
        if existing is not None:
            if existing != family:
                raise ValueError(f"conflicting cognitive operator family: {family.family_id}")
            return
        occupied = {
            sub.operator_id
            for registered in self._families.values()
            for sub in registered.suboperators
        }
        duplicate_ids = sorted(occupied.intersection(sub.operator_id for sub in family.suboperators))
        if duplicate_ids:
            raise ValueError(f"conflicting cognitive operator ids: {duplicate_ids}")
        self._families[family.family_id] = family

    def register_abstraction(self, abstraction: LearnedAbstraction) -> None:
        self._vocabulary.register(abstraction)

    def families(self) -> tuple[OperatorFamilyDescriptor, ...]:
        return tuple(self._families[key] for key in sorted(self._families))

    def family(self, family_id: str) -> OperatorFamilyDescriptor:
        key = str(family_id)
        try:
            return self._families[key]
        except KeyError:
            raise KeyError(key) from None

    def operator(self, operator_id: str) -> SubOperatorDescriptor:
        key = str(operator_id)
        for family in self.families():
            for row in family.suboperators:
                if row.operator_id == key:
                    return row
        raise KeyError(key)

    def to_state(self) -> dict[str, Any]:
        return {
            "schema_version": "cognitive-library-v1",
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "families": [_family_state(row) for row in self.families()],
            "abstractions": [_abstraction_state(row) for row in self._vocabulary.abstractions()],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CognitiveLibrary":
        if str(state.get("schema_version")) != "cognitive-library-v1":
            raise ValueError("unsupported cognitive library schema")
        if str(state.get("component_id")) != COMPONENT_ID:
            raise ValueError("cognitive library component mismatch")
        if str(state.get("component_version")) != COMPONENT_VERSION:
            raise ValueError("cognitive library component version mismatch")

        families: list[OperatorFamilyDescriptor] = []
        for family_state in state.get("families", ()):
            family_data = dict(family_state)
            suboperators = tuple(
                SubOperatorDescriptor(
                    str(item["operator_id"]),
                    str(item["status"]),
                    str(item["summary"]),
                    frozenset(str(tag) for tag in item.get("tags", ())),
                )
                for item in family_data.get("suboperators", ())
            )
            families.append(
                OperatorFamilyDescriptor(
                    str(family_data["family_id"]),
                    str(family_data["summary"]),
                    suboperators,
                )
            )

        abstractions = tuple(
            LearnedAbstraction(
                str(item["abstraction_id"]),
                int(item["parameter_count"]),
                _expr_from_data(item["template"]),
                tuple(str(task_id) for task_id in item.get("support_task_ids", ())),
                int(item["raw_occurrence_cost"]),
                int(item["rewritten_cost"]),
            )
            for item in state.get("abstractions", ())
        )
        result = cls(families=families, abstractions=abstractions)
        if result.to_state() != dict(state):
            raise ValueError("non-canonical cognitive library state")
        return result


__all__ = (
    "CognitiveLibrary",
    "OperatorFamilyDescriptor",
    "SubOperatorDescriptor",
    "LearnedAbstraction",
    "CognitiveVocabulary",
)
