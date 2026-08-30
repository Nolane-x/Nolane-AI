from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Iterable

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt

from .cognitive_catalog import OperatorFamilyDescriptor, SubOperatorDescriptor, build_default_externalization_catalog
from .cognitive_operators import Binary, Const, Expr, Field, IfElse, Unary
from .cognitive_vocabulary import (
    AbstractionCall,
    CognitiveVocabulary,
    LearnedAbstraction,
    TemplateParam,
)


COMPONENT_ID = "external.cognitive_library"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder R2.53/R2.56/R2.57 cognitive-library lineage"
_SCHEMA_VERSION = "cognitive-library-v2"
_LEGACY_SCHEMA_VERSION = "cognitive-library-v1"


def _clean_id(value: object, *, field: str) -> str:
    clean = str(value).strip()
    if not clean:
        raise ValueError(f"{field} must be non-empty")
    return clean


def _ordered_ids(values: Iterable[object], *, field: str, allow_empty: bool = True) -> tuple[str, ...]:
    rows = tuple(_clean_id(value, field=field) for value in values)
    if not allow_empty and not rows:
        raise ValueError(f"{field} must be non-empty")
    if len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be unique")
    return rows


def _set_ids(values: Iterable[object], *, field: str, allow_empty: bool = True) -> tuple[str, ...]:
    return tuple(sorted(_ordered_ids(values, field=field, allow_empty=allow_empty)))


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


def _family_from_state(state: Mapping[str, Any]) -> OperatorFamilyDescriptor:
    family_data = dict(state)
    suboperators = tuple(
        SubOperatorDescriptor(
            str(item["operator_id"]),
            str(item["status"]),
            str(item["summary"]),
            frozenset(str(tag) for tag in item.get("tags", ())),
        )
        for item in family_data.get("suboperators", ())
    )
    return OperatorFamilyDescriptor(
        str(family_data["family_id"]),
        str(family_data["summary"]),
        suboperators,
    )


def _abstraction_from_state(state: Mapping[str, Any]) -> LearnedAbstraction:
    item = dict(state)
    return LearnedAbstraction(
        str(item["abstraction_id"]),
        int(item["parameter_count"]),
        _expr_from_data(item["template"]),
        tuple(str(task_id) for task_id in item.get("support_task_ids", ())),
        int(item["raw_occurrence_cost"]),
        int(item["rewritten_cost"]),
    )


def _capability_candidate_id(kind: str, payload: Mapping[str, Any]) -> str:
    semantic = {"kind": str(kind), "payload": dict(payload)}
    return f"capability:{canonical_digest(semantic)}"


@dataclass(frozen=True, slots=True)
class CognitiveCapabilityDescriptor:
    descriptor_id: str
    capability_id: str
    kind: str
    candidate_id: str
    payload_digest: str
    predecessor_digest: str
    assurance_receipt_id: str
    evidence_ids: tuple[str, ...]
    verifier_ids: tuple[str, ...]
    support_task_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        kind = _clean_id(self.kind, field="descriptor kind")
        if kind not in {"operator_family", "learned_abstraction"}:
            raise ValueError("unsupported cognitive capability descriptor kind")
        capability_id = _clean_id(self.capability_id, field="capability_id")
        candidate_id = _clean_id(self.candidate_id, field="candidate_id")
        payload_digest = _clean_id(self.payload_digest, field="payload_digest")
        predecessor_digest = _clean_id(self.predecessor_digest, field="predecessor_digest")
        receipt_id = _clean_id(self.assurance_receipt_id, field="assurance_receipt_id")
        evidence_ids = _ordered_ids(self.evidence_ids, field="descriptor evidence ids", allow_empty=False)
        verifier_ids = _ordered_ids(self.verifier_ids, field="descriptor verifier ids", allow_empty=False)
        support_task_ids = _set_ids(self.support_task_ids, field="descriptor support task ids")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "capability_id", capability_id)
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "payload_digest", payload_digest)
        object.__setattr__(self, "predecessor_digest", predecessor_digest)
        object.__setattr__(self, "assurance_receipt_id", receipt_id)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "verifier_ids", verifier_ids)
        object.__setattr__(self, "support_task_ids", support_task_ids)
        expected = f"cognitive-capability:{canonical_digest(self.semantic_state())}"
        if str(self.descriptor_id) != expected:
            raise ValueError("cognitive capability descriptor identity mismatch")
        object.__setattr__(self, "descriptor_id", expected)

    def semantic_state(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "kind": self.kind,
            "candidate_id": self.candidate_id,
            "payload_digest": self.payload_digest,
            "predecessor_digest": self.predecessor_digest,
            "assurance_receipt_id": self.assurance_receipt_id,
            "evidence_ids": list(self.evidence_ids),
            "verifier_ids": list(self.verifier_ids),
            "support_task_ids": list(self.support_task_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {"descriptor_id": self.descriptor_id, **self.semantic_state()}

    @classmethod
    def create(
        cls,
        *,
        capability_id: str,
        kind: str,
        candidate_id: str,
        payload_digest: str,
        predecessor_digest: str,
        assurance_receipt_id: str,
        evidence_ids: tuple[str, ...],
        verifier_ids: tuple[str, ...],
        support_task_ids: tuple[str, ...] = (),
    ) -> "CognitiveCapabilityDescriptor":
        semantic = {
            "capability_id": _clean_id(capability_id, field="capability_id"),
            "kind": _clean_id(kind, field="descriptor kind"),
            "candidate_id": _clean_id(candidate_id, field="candidate_id"),
            "payload_digest": _clean_id(payload_digest, field="payload_digest"),
            "predecessor_digest": _clean_id(predecessor_digest, field="predecessor_digest"),
            "assurance_receipt_id": _clean_id(assurance_receipt_id, field="assurance_receipt_id"),
            "evidence_ids": list(_ordered_ids(evidence_ids, field="descriptor evidence ids", allow_empty=False)),
            "verifier_ids": list(_ordered_ids(verifier_ids, field="descriptor verifier ids", allow_empty=False)),
            "support_task_ids": list(_set_ids(support_task_ids, field="descriptor support task ids")),
        }
        return cls(
            descriptor_id=f"cognitive-capability:{canonical_digest(semantic)}",
            capability_id=str(semantic["capability_id"]),
            kind=str(semantic["kind"]),
            candidate_id=str(semantic["candidate_id"]),
            payload_digest=str(semantic["payload_digest"]),
            predecessor_digest=str(semantic["predecessor_digest"]),
            assurance_receipt_id=str(semantic["assurance_receipt_id"]),
            evidence_ids=tuple(str(value) for value in semantic["evidence_ids"]),
            verifier_ids=tuple(str(value) for value in semantic["verifier_ids"]),
            support_task_ids=tuple(str(value) for value in semantic["support_task_ids"]),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CognitiveCapabilityDescriptor":
        row = cls(
            descriptor_id=str(state["descriptor_id"]),
            capability_id=str(state["capability_id"]),
            kind=str(state["kind"]),
            candidate_id=str(state["candidate_id"]),
            payload_digest=str(state["payload_digest"]),
            predecessor_digest=str(state["predecessor_digest"]),
            assurance_receipt_id=str(state["assurance_receipt_id"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            verifier_ids=tuple(str(value) for value in state.get("verifier_ids", ())),
            support_task_ids=tuple(str(value) for value in state.get("support_task_ids", ())),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical cognitive capability descriptor state")
        return row


@dataclass(frozen=True, slots=True)
class LibraryFitReport:
    library_digest: str
    required_operator_ids: tuple[str, ...]
    required_abstraction_ids: tuple[str, ...]
    matched_operator_ids: tuple[str, ...]
    missing_operator_ids: tuple[str, ...]
    matched_abstraction_ids: tuple[str, ...]
    missing_abstraction_ids: tuple[str, ...]
    descriptor_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        library_digest = _clean_id(self.library_digest, field="library_digest")
        required_operators = _set_ids(self.required_operator_ids, field="required operator ids")
        required_abstractions = _set_ids(self.required_abstraction_ids, field="required abstraction ids")
        if not required_operators and not required_abstractions:
            raise ValueError("fit diagnostics require at least one capability id")
        matched_operators = _set_ids(self.matched_operator_ids, field="matched operator ids")
        missing_operators = _set_ids(self.missing_operator_ids, field="missing operator ids")
        matched_abstractions = _set_ids(self.matched_abstraction_ids, field="matched abstraction ids")
        missing_abstractions = _set_ids(self.missing_abstraction_ids, field="missing abstraction ids")
        descriptor_ids = _set_ids(self.descriptor_ids, field="descriptor ids")
        if set(matched_operators).intersection(missing_operators):
            raise ValueError("operator fit partitions overlap")
        if set(matched_abstractions).intersection(missing_abstractions):
            raise ValueError("abstraction fit partitions overlap")
        if set(matched_operators).union(missing_operators) != set(required_operators):
            raise ValueError("operator fit partition mismatch")
        if set(matched_abstractions).union(missing_abstractions) != set(required_abstractions):
            raise ValueError("abstraction fit partition mismatch")
        object.__setattr__(self, "library_digest", library_digest)
        object.__setattr__(self, "required_operator_ids", required_operators)
        object.__setattr__(self, "required_abstraction_ids", required_abstractions)
        object.__setattr__(self, "matched_operator_ids", matched_operators)
        object.__setattr__(self, "missing_operator_ids", missing_operators)
        object.__setattr__(self, "matched_abstraction_ids", matched_abstractions)
        object.__setattr__(self, "missing_abstraction_ids", missing_abstractions)
        object.__setattr__(self, "descriptor_ids", descriptor_ids)

    @property
    def required_count(self) -> int:
        return len(self.required_operator_ids) + len(self.required_abstraction_ids)

    @property
    def matched_count(self) -> int:
        return len(self.matched_operator_ids) + len(self.matched_abstraction_ids)

    @property
    def coverage(self) -> float:
        return self.matched_count / self.required_count

    @property
    def complete(self) -> bool:
        return not self.missing_operator_ids and not self.missing_abstraction_ids

    def to_state(self) -> dict[str, Any]:
        return {
            "library_digest": self.library_digest,
            "required_operator_ids": list(self.required_operator_ids),
            "required_abstraction_ids": list(self.required_abstraction_ids),
            "matched_operator_ids": list(self.matched_operator_ids),
            "missing_operator_ids": list(self.missing_operator_ids),
            "matched_abstraction_ids": list(self.matched_abstraction_ids),
            "missing_abstraction_ids": list(self.missing_abstraction_ids),
            "descriptor_ids": list(self.descriptor_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "LibraryFitReport":
        row = cls(
            library_digest=str(state["library_digest"]),
            required_operator_ids=tuple(str(value) for value in state.get("required_operator_ids", ())),
            required_abstraction_ids=tuple(str(value) for value in state.get("required_abstraction_ids", ())),
            matched_operator_ids=tuple(str(value) for value in state.get("matched_operator_ids", ())),
            missing_operator_ids=tuple(str(value) for value in state.get("missing_operator_ids", ())),
            matched_abstraction_ids=tuple(str(value) for value in state.get("matched_abstraction_ids", ())),
            missing_abstraction_ids=tuple(str(value) for value in state.get("missing_abstraction_ids", ())),
            descriptor_ids=tuple(str(value) for value in state.get("descriptor_ids", ())),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical cognitive library fit state")
        return row


class CognitiveVocabularyView:
    """Read-only projection of the learned-abstraction vocabulary."""

    __slots__ = ("__vocabulary",)

    def __init__(self, vocabulary: CognitiveVocabulary) -> None:
        self.__vocabulary = vocabulary

    def get(self, abstraction_id: str) -> LearnedAbstraction:
        return self.__vocabulary.get(abstraction_id)

    def abstractions(self) -> tuple[LearnedAbstraction, ...]:
        return self.__vocabulary.abstractions()


class CognitiveLibrary:
    """Canonical registry for reusable cognition with fail-closed live writes.

    Constructor/from-state inputs are bootstrap or restore material. Runtime growth
    must carry an exact persisted Assurance promotion receipt bound to the candidate
    payload and the current library digest. Retrieval and fit diagnostics are
    read-only and never grant promotion authority.
    """

    def __init__(
        self,
        *,
        families: Iterable[OperatorFamilyDescriptor] = (),
        abstractions: Iterable[LearnedAbstraction] = (),
        descriptors: Iterable[CognitiveCapabilityDescriptor] = (),
    ) -> None:
        self._families: dict[str, OperatorFamilyDescriptor] = {}
        self._vocabulary = CognitiveVocabulary()
        self._descriptors: dict[str, CognitiveCapabilityDescriptor] = {}
        self._descriptor_by_candidate: dict[str, str] = {}
        for family in families:
            self._register_family_unchecked(family)
        for abstraction in abstractions:
            self._register_abstraction_unchecked(abstraction)
        for descriptor in descriptors:
            self._restore_descriptor(descriptor)

    @classmethod
    def with_defaults(cls) -> "CognitiveLibrary":
        return cls(families=build_default_externalization_catalog())

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @property
    def vocabulary(self) -> CognitiveVocabularyView:
        return CognitiveVocabularyView(self._vocabulary)

    def _register_family_unchecked(self, family: OperatorFamilyDescriptor) -> None:
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

    def _register_abstraction_unchecked(self, abstraction: LearnedAbstraction) -> None:
        self._vocabulary.register(abstraction)

    def _validate_promotion_authority(
        self,
        *,
        kind: str,
        payload: Mapping[str, Any],
        candidate_id: str,
        assurance: AssuranceControlPlane,
        receipt: PromotionAssuranceReceipt,
    ) -> PromotionAssuranceReceipt:
        if not isinstance(assurance, AssuranceControlPlane):
            raise TypeError("assurance must be native AssuranceControlPlane")
        if not isinstance(receipt, PromotionAssuranceReceipt):
            raise TypeError("receipt must be PromotionAssuranceReceipt")
        clean_candidate = _clean_id(candidate_id, field="candidate_id")
        expected_candidate = _capability_candidate_id(kind, payload)
        if clean_candidate != expected_candidate:
            raise ValueError("cognitive capability candidate identity mismatch")
        PromotionAssuranceReceipt.from_state(receipt.to_state())
        try:
            persisted = AssuranceControlPlane.promotion_receipt(assurance, receipt.receipt_id)
        except (KeyError, LookupError) as exc:
            raise ValueError("persisted assurance receipt is required") from exc
        if not isinstance(persisted, PromotionAssuranceReceipt):
            raise ValueError("persisted assurance receipt has invalid type")
        PromotionAssuranceReceipt.from_state(persisted.to_state())
        if persisted != receipt:
            raise ValueError("persisted assurance receipt does not match supplied receipt")
        if not persisted.authorized:
            raise ValueError("promotion assurance receipt is not authorized")
        if persisted.subject_id != clean_candidate:
            raise ValueError("promotion assurance receipt subject/candidate mismatch")
        if persisted.predecessor_version != self.digest:
            raise ValueError("promotion assurance receipt predecessor baseline mismatch")
        return persisted

    @staticmethod
    def _descriptor_for_promotion(
        *,
        kind: str,
        capability_id: str,
        payload: Mapping[str, Any],
        candidate_id: str,
        receipt: PromotionAssuranceReceipt,
        support_task_ids: tuple[str, ...] = (),
    ) -> CognitiveCapabilityDescriptor:
        return CognitiveCapabilityDescriptor.create(
            capability_id=capability_id,
            kind=kind,
            candidate_id=candidate_id,
            payload_digest=canonical_digest(dict(payload)),
            predecessor_digest=receipt.predecessor_version,
            assurance_receipt_id=receipt.receipt_id,
            evidence_ids=tuple(receipt.evidence_ids),
            verifier_ids=tuple(receipt.verifier_ids),
            support_task_ids=support_task_ids,
        )

    def _validate_descriptor_binding(self, descriptor: CognitiveCapabilityDescriptor) -> None:
        if descriptor.kind == "operator_family":
            payload = _family_state(self.family(descriptor.capability_id))
        else:
            payload = _abstraction_state(self._vocabulary.get(descriptor.capability_id))
        if canonical_digest(payload) != descriptor.payload_digest:
            raise ValueError("cognitive capability descriptor payload mismatch")
        if _capability_candidate_id(descriptor.kind, payload) != descriptor.candidate_id:
            raise ValueError("cognitive capability descriptor candidate mismatch")

    def _restore_descriptor(self, descriptor: CognitiveCapabilityDescriptor) -> None:
        if not isinstance(descriptor, CognitiveCapabilityDescriptor):
            raise TypeError("descriptors must contain CognitiveCapabilityDescriptor values")
        self._validate_descriptor_binding(descriptor)
        existing = self._descriptors.get(descriptor.descriptor_id)
        if existing is not None:
            if existing != descriptor:
                raise ValueError("cognitive capability descriptor collision")
            return
        prior = self._descriptor_by_candidate.get(descriptor.candidate_id)
        if prior is not None and prior != descriptor.descriptor_id:
            raise ValueError("candidate already has a cognitive capability descriptor")
        self._descriptors[descriptor.descriptor_id] = descriptor
        self._descriptor_by_candidate[descriptor.candidate_id] = descriptor.descriptor_id

    def register_family(
        self,
        family: OperatorFamilyDescriptor,
        *,
        candidate_id: str,
        assurance: AssuranceControlPlane,
        receipt: PromotionAssuranceReceipt,
    ) -> CognitiveCapabilityDescriptor:
        if not isinstance(family, OperatorFamilyDescriptor):
            raise TypeError("family must be OperatorFamilyDescriptor")
        if family.family_id in self._families:
            existing = self._families[family.family_id]
            if existing != family:
                raise ValueError(f"conflicting cognitive operator family: {family.family_id}")
            raise ValueError("cognitive capability is already installed")
        payload = _family_state(family)
        persisted = self._validate_promotion_authority(
            kind="operator_family",
            payload=payload,
            candidate_id=candidate_id,
            assurance=assurance,
            receipt=receipt,
        )
        descriptor = self._descriptor_for_promotion(
            kind="operator_family",
            capability_id=family.family_id,
            payload=payload,
            candidate_id=str(candidate_id).strip(),
            receipt=persisted,
        )
        if descriptor.candidate_id in self._descriptor_by_candidate:
            raise ValueError("candidate already has a cognitive capability descriptor")
        self._register_family_unchecked(family)
        self._restore_descriptor(descriptor)
        return descriptor

    def register_abstraction(
        self,
        abstraction: LearnedAbstraction,
        *,
        candidate_id: str,
        assurance: AssuranceControlPlane,
        receipt: PromotionAssuranceReceipt,
    ) -> CognitiveCapabilityDescriptor:
        if not isinstance(abstraction, LearnedAbstraction):
            raise TypeError("abstraction must be LearnedAbstraction")
        try:
            existing = self._vocabulary.get(abstraction.abstraction_id)
        except KeyError:
            existing = None
        if existing is not None:
            if existing != abstraction:
                raise ValueError("abstraction digest collision")
            raise ValueError("cognitive capability is already installed")
        payload = _abstraction_state(abstraction)
        persisted = self._validate_promotion_authority(
            kind="learned_abstraction",
            payload=payload,
            candidate_id=candidate_id,
            assurance=assurance,
            receipt=receipt,
        )
        descriptor = self._descriptor_for_promotion(
            kind="learned_abstraction",
            capability_id=abstraction.abstraction_id,
            payload=payload,
            candidate_id=str(candidate_id).strip(),
            receipt=persisted,
            support_task_ids=abstraction.support_task_ids,
        )
        if descriptor.candidate_id in self._descriptor_by_candidate:
            raise ValueError("candidate already has a cognitive capability descriptor")
        self._register_abstraction_unchecked(abstraction)
        self._restore_descriptor(descriptor)
        return descriptor

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

    def capability_descriptors(self) -> tuple[CognitiveCapabilityDescriptor, ...]:
        return tuple(self._descriptors[key] for key in sorted(self._descriptors))

    def descriptor(self, descriptor_id: str) -> CognitiveCapabilityDescriptor:
        key = str(descriptor_id)
        try:
            return self._descriptors[key]
        except KeyError:
            raise KeyError(key) from None

    def descriptor_for_candidate(self, candidate_id: str) -> CognitiveCapabilityDescriptor:
        key = str(candidate_id)
        try:
            descriptor_id = self._descriptor_by_candidate[key]
        except KeyError:
            raise KeyError(key) from None
        return self._descriptors[descriptor_id]

    def _family_id_for_operator(self, operator_id: str) -> str | None:
        key = str(operator_id)
        for family in self.families():
            if any(row.operator_id == key for row in family.suboperators):
                return family.family_id
        return None

    def diagnose_fit(
        self,
        *,
        operator_ids: Iterable[str] = (),
        abstraction_ids: Iterable[str] = (),
    ) -> LibraryFitReport:
        required_operators = _set_ids(operator_ids, field="required operator ids")
        required_abstractions = _set_ids(abstraction_ids, field="required abstraction ids")
        if not required_operators and not required_abstractions:
            raise ValueError("fit diagnostics require at least one capability id")
        baseline = self.digest
        matched_operators: list[str] = []
        missing_operators: list[str] = []
        matched_abstractions: list[str] = []
        missing_abstractions: list[str] = []
        descriptor_ids: set[str] = set()

        for operator_id in required_operators:
            family_id = self._family_id_for_operator(operator_id)
            if family_id is None:
                missing_operators.append(operator_id)
                continue
            matched_operators.append(operator_id)
            for descriptor in self._descriptors.values():
                if descriptor.kind == "operator_family" and descriptor.capability_id == family_id:
                    descriptor_ids.add(descriptor.descriptor_id)

        for abstraction_id in required_abstractions:
            try:
                self._vocabulary.get(abstraction_id)
            except KeyError:
                missing_abstractions.append(abstraction_id)
                continue
            matched_abstractions.append(abstraction_id)
            for descriptor in self._descriptors.values():
                if descriptor.kind == "learned_abstraction" and descriptor.capability_id == abstraction_id:
                    descriptor_ids.add(descriptor.descriptor_id)

        return LibraryFitReport(
            library_digest=baseline,
            required_operator_ids=required_operators,
            required_abstraction_ids=required_abstractions,
            matched_operator_ids=tuple(matched_operators),
            missing_operator_ids=tuple(missing_operators),
            matched_abstraction_ids=tuple(matched_abstractions),
            missing_abstraction_ids=tuple(missing_abstractions),
            descriptor_ids=tuple(sorted(descriptor_ids)),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "families": [_family_state(row) for row in self.families()],
            "abstractions": [_abstraction_state(row) for row in self._vocabulary.abstractions()],
            "descriptors": [row.to_state() for row in self.capability_descriptors()],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CognitiveLibrary":
        schema_version = str(state.get("schema_version"))
        if schema_version not in {_SCHEMA_VERSION, _LEGACY_SCHEMA_VERSION}:
            raise ValueError("unsupported cognitive library schema")
        if str(state.get("component_id")) != COMPONENT_ID:
            raise ValueError("cognitive library component mismatch")
        component_version = str(state.get("component_version"))
        if schema_version == _SCHEMA_VERSION:
            if component_version != COMPONENT_VERSION:
                raise ValueError("cognitive library component version mismatch")
        elif component_version not in {"0.0.1", COMPONENT_VERSION}:
            raise ValueError("cognitive library component version mismatch")

        families = tuple(_family_from_state(row) for row in state.get("families", ()))
        abstractions = tuple(_abstraction_from_state(row) for row in state.get("abstractions", ()))
        descriptors = (
            tuple(CognitiveCapabilityDescriptor.from_state(row) for row in state.get("descriptors", ()))
            if schema_version == _SCHEMA_VERSION
            else ()
        )
        result = cls(families=families, abstractions=abstractions, descriptors=descriptors)
        if schema_version == _SCHEMA_VERSION and result.to_state() != dict(state):
            raise ValueError("non-canonical cognitive library state")
        return result


__all__ = (
    "CognitiveLibrary",
    "CognitiveCapabilityDescriptor",
    "LibraryFitReport",
    "CognitiveVocabularyView",
    "OperatorFamilyDescriptor",
    "SubOperatorDescriptor",
    "LearnedAbstraction",
    "CognitiveVocabulary",
)
