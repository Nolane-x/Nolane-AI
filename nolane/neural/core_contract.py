from __future__ import annotations

import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest, canonical_json


COMPONENT_ID = "neural.core_contract"
COMPONENT_VERSION = "0.0.1"
NEURAL_CORE_REVISION = "R2.4"

_AUTHORITATIVE_DOMAINS = frozenset({"truth", "verification", "assurance"})
_PROTECTED_ADAPTATION_PREFIXES = (
    "truth.",
    "verification.",
    "assurance.",
    "external.authority",
)
_EVIDENCE_STATE_FIELDS = frozenset({"source_core", "receipt_id", "digest", "authority"})
_COGNITIVE_STATE_FIELDS = frozenset({"revision", "payload", "provenance", "digest"})


class NeuralInvariantError(ValueError):
    """Raised when a Neural Core boundary or determinism invariant is violated."""


def _nonempty(value: object, field: str) -> str:
    if value is None:
        raise NeuralInvariantError(f"{field} must be explicit and non-empty")
    text = str(value).strip()
    if not text:
        raise NeuralInvariantError(f"{field} must be explicit and non-empty")
    return text


def _confidence(value: float, field: str = "confidence") -> float:
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise NeuralInvariantError(f"{field} must be a finite normalized value in [0, 1]")
    return score


def _digest(value: object, field: str = "digest") -> str:
    text = _nonempty(value, field)
    if text != text.lower():
        raise NeuralInvariantError(f"{field} must be a 64-character lowercase SHA-256 digest")
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise NeuralInvariantError(f"{field} must be a 64-character lowercase SHA-256 digest")
    return text


def _evidence_rows(values: Iterable["EvidenceRef"], field: str) -> tuple["EvidenceRef", ...]:
    rows = tuple(values)
    if not rows:
        raise NeuralInvariantError(f"{field} must be non-empty")
    if any(not isinstance(row, EvidenceRef) for row in rows):
        raise NeuralInvariantError(f"{field} must contain EvidenceRef values only")
    return tuple(sorted(rows, key=lambda row: canonical_json(row.to_state())))


def _is_neural_source(source: str) -> bool:
    return source == "neural" or source.startswith(("neural.", "neural-", "nolane.neural", "nolane-neural"))


def _canonical_parameter(value: object) -> str:
    return _nonempty(value, "adaptation parameter").lower()


def _is_protected_parameter(name: str) -> bool:
    return name.startswith(_PROTECTED_ADAPTATION_PREFIXES)


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Reference to evidence issued elsewhere; it never grants Neural authority to mint that evidence."""

    source_core: str
    receipt_id: str
    digest: str
    authority: str

    @classmethod
    def create(
        cls,
        *,
        source_core: str,
        receipt_id: str,
        digest: str,
        authority: str = "observation",
    ) -> "EvidenceRef":
        source = _nonempty(source_core, "source_core").lower()
        authority_name = _nonempty(authority, "authority").lower()
        if _is_neural_source(source) and authority_name in _AUTHORITATIVE_DOMAINS:
            raise NeuralInvariantError(
                f"Neural Core cannot mint {authority_name} authority; it may only reference externally issued evidence"
            )
        return cls(
            source_core=source,
            receipt_id=_nonempty(receipt_id, "receipt_id"),
            digest=_digest(digest),
            authority=authority_name,
        )

    def to_state(self) -> dict[str, str]:
        return {
            "source_core": self.source_core,
            "receipt_id": self.receipt_id,
            "digest": self.digest,
            "authority": self.authority,
        }


@dataclass(frozen=True, slots=True)
class CognitiveState:
    """Canonical, immutable cognition payload whose identity includes provenance."""

    _payload_json: str
    provenance: tuple[EvidenceRef, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        payload: Mapping[str, Any],
        provenance: Iterable[EvidenceRef],
    ) -> "CognitiveState":
        if not isinstance(payload, Mapping) or not payload:
            raise NeuralInvariantError("cognitive payload must be a non-empty mapping")
        ordered = _evidence_rows(provenance, "cognitive provenance")
        payload_json = canonical_json(dict(payload))
        canonical_payload = json.loads(payload_json)
        state_digest = canonical_digest(
            {
                "payload": canonical_payload,
                "provenance": [row.to_state() for row in ordered],
                "revision": NEURAL_CORE_REVISION,
            }
        )
        return cls(_payload_json=payload_json, provenance=ordered, digest=state_digest)

    @property
    def payload(self) -> Mapping[str, Any]:
        return MappingProxyType(json.loads(self._payload_json))

    def to_state(self) -> dict[str, Any]:
        return {
            "revision": NEURAL_CORE_REVISION,
            "payload": json.loads(self._payload_json),
            "provenance": [row.to_state() for row in self.provenance],
            "digest": self.digest,
        }

    def bind_context_digest(self, capsule_digest: str) -> str:
        """Bind R2.4 cognition/provenance identity to a pre-existing context capsule digest."""
        return canonical_digest(
            {
                "capsule_digest": _digest(capsule_digest, "capsule digest"),
                "cognitive_state_digest": self.digest,
                "neural_core_revision": NEURAL_CORE_REVISION,
            }
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CognitiveState":
        if not isinstance(state, Mapping):
            raise NeuralInvariantError("cognitive state must be a mapping")
        missing_state_fields = sorted(_COGNITIVE_STATE_FIELDS.difference(state.keys()))
        if missing_state_fields:
            raise NeuralInvariantError(
                "cognitive state missing fields: " + ", ".join(missing_state_fields)
            )
        unknown_state_fields = sorted(set(state.keys()).difference(_COGNITIVE_STATE_FIELDS))
        if unknown_state_fields:
            raise NeuralInvariantError(
                "cognitive state has unknown fields: " + ", ".join(str(x) for x in unknown_state_fields)
            )
        if state["revision"] != NEURAL_CORE_REVISION:
            raise NeuralInvariantError("cognitive state revision mismatch")
        raw_provenance = state["provenance"]
        if not isinstance(raw_provenance, Sequence) or isinstance(raw_provenance, (str, bytes)):
            raise NeuralInvariantError("cognitive provenance must be explicit")
        provenance: list[EvidenceRef] = []
        for index, row in enumerate(raw_provenance):
            if not isinstance(row, Mapping):
                raise NeuralInvariantError(f"cognitive provenance entry {index} must be a mapping")
            missing = sorted(_EVIDENCE_STATE_FIELDS.difference(row.keys()))
            if missing:
                raise NeuralInvariantError(
                    f"cognitive provenance entry {index} missing fields: " + ", ".join(missing)
                )
            unknown = sorted(set(row.keys()).difference(_EVIDENCE_STATE_FIELDS))
            if unknown:
                raise NeuralInvariantError(
                    f"cognitive provenance entry {index} has unknown fields: " + ", ".join(str(x) for x in unknown)
                )
            provenance.append(
                EvidenceRef.create(
                    source_core=row["source_core"],
                    receipt_id=row["receipt_id"],
                    digest=row["digest"],
                    authority=row["authority"],
                )
            )
        rebuilt = cls.create(payload=state["payload"], provenance=provenance)
        claimed_digest = _digest(state["digest"], "cognitive state digest")
        if rebuilt.digest != claimed_digest:
            raise NeuralInvariantError("cognitive state digest/provenance mismatch; possible state laundering")
        return rebuilt


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    value: float
    abstain: bool
    reason: str | None
    threshold: float

    @classmethod
    def create(cls, value: float, *, abstain_below: float = 0.0) -> "ConfidenceAssessment":
        score = _confidence(value)
        threshold = _confidence(abstain_below, "abstention threshold")
        abstain = score < threshold
        return cls(
            value=score,
            abstain=abstain,
            reason="below-confidence-threshold" if abstain else None,
            threshold=threshold,
        )


@dataclass(frozen=True, slots=True)
class ExpertRoute:
    expert_id: str
    path_id: str
    confidence: float
    evidence: tuple[EvidenceRef, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        expert_id: str,
        path_id: str,
        confidence: float,
        evidence: Iterable[EvidenceRef],
    ) -> "ExpertRoute":
        expert = _nonempty(expert_id, "expert_id")
        path = _nonempty(path_id, "path_id")
        score = _confidence(confidence)
        ordered = _evidence_rows(evidence, "expert route evidence")
        digest = canonical_digest(
            {
                "expert_id": expert,
                "path_id": path,
                "confidence": score,
                "evidence": [row.to_state() for row in ordered],
            }
        )
        return cls(expert_id=expert, path_id=path, confidence=score, evidence=ordered, digest=digest)


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    ranked: tuple[ExpertRoute, ...]
    selected: ExpertRoute | None
    abstain: bool
    reason: str | None


class ExpertRouter:
    """Stateless multi-expert router with deterministic ranking and explicit abstention."""

    @staticmethod
    def rank(routes: Iterable[ExpertRoute]) -> tuple[ExpertRoute, ...]:
        rows = tuple(routes)
        if any(not isinstance(row, ExpertRoute) for row in rows):
            raise NeuralInvariantError("expert routes must contain ExpertRoute values only")
        identities = tuple((row.expert_id, row.path_id) for row in rows)
        if len(set(identities)) != len(identities):
            raise NeuralInvariantError("expert route identities must be unique")
        return tuple(
            sorted(
                rows,
                key=lambda row: (
                    -row.confidence,
                    row.expert_id,
                    row.path_id,
                    row.digest,
                ),
            )
        )

    @classmethod
    def select(
        cls,
        routes: Iterable[ExpertRoute],
        *,
        min_confidence: float,
        min_margin: float,
    ) -> RoutingDecision:
        threshold = _confidence(min_confidence, "minimum route confidence")
        margin = _confidence(min_margin, "minimum route confidence margin")
        ranked = cls.rank(routes)
        if not ranked:
            return RoutingDecision(ranked=ranked, selected=None, abstain=True, reason="no-routes")
        top = ranked[0]
        if top.confidence < threshold:
            return RoutingDecision(
                ranked=ranked,
                selected=None,
                abstain=True,
                reason="below-confidence-threshold",
            )
        if len(ranked) > 1 and top.confidence - ranked[1].confidence < margin:
            return RoutingDecision(
                ranked=ranked,
                selected=None,
                abstain=True,
                reason="insufficient-confidence-margin",
            )
        return RoutingDecision(ranked=ranked, selected=top, abstain=False, reason=None)


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    route: ExpertRoute
    confidence: float
    utility: float
    evidence: tuple[EvidenceRef, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        route: ExpertRoute,
        confidence: float,
        utility: float,
        evidence: Iterable[EvidenceRef],
    ) -> "Candidate":
        if not isinstance(route, ExpertRoute):
            raise NeuralInvariantError("candidate route must be an ExpertRoute")
        cid = _nonempty(candidate_id, "candidate_id")
        confidence_value = _confidence(confidence)
        utility_value = _confidence(utility, "utility")
        ordered = _evidence_rows(evidence, "candidate evidence")
        digest = canonical_digest(
            {
                "candidate_id": cid,
                "route_digest": route.digest,
                "confidence": confidence_value,
                "utility": utility_value,
                "evidence": [row.to_state() for row in ordered],
            }
        )
        return cls(
            candidate_id=cid,
            route=route,
            confidence=confidence_value,
            utility=utility_value,
            evidence=ordered,
            digest=digest,
        )


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    ranked: tuple[Candidate, ...]
    selected: Candidate | None
    abstain: bool
    reason: str | None


class CandidateRanker:
    """Stateless deterministic ranker. No candidate may mutate global routing authority."""

    @staticmethod
    def rank(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
        rows = tuple(candidates)
        if any(not isinstance(row, Candidate) for row in rows):
            raise NeuralInvariantError("candidates must contain Candidate values only")
        if len({row.candidate_id for row in rows}) != len(rows):
            raise NeuralInvariantError("candidate ids must be unique")
        return tuple(
            sorted(
                rows,
                key=lambda row: (
                    -row.confidence,
                    -row.utility,
                    -row.route.confidence,
                    row.candidate_id,
                    row.route.expert_id,
                    row.route.path_id,
                    row.digest,
                ),
            )
        )

    @classmethod
    def select(
        cls,
        candidates: Iterable[Candidate],
        *,
        min_confidence: float,
        min_margin: float,
    ) -> CandidateDecision:
        threshold = _confidence(min_confidence, "minimum confidence")
        margin = _confidence(min_margin, "minimum confidence margin")
        ranked = cls.rank(candidates)
        if not ranked:
            return CandidateDecision(ranked=ranked, selected=None, abstain=True, reason="no-candidates")
        top = ranked[0]
        if top.confidence < threshold:
            return CandidateDecision(
                ranked=ranked,
                selected=None,
                abstain=True,
                reason="below-confidence-threshold",
            )
        if len(ranked) > 1 and top.confidence - ranked[1].confidence < margin:
            return CandidateDecision(
                ranked=ranked,
                selected=None,
                abstain=True,
                reason="insufficient-confidence-margin",
            )
        return CandidateDecision(ranked=ranked, selected=top, abstain=False, reason=None)


@dataclass(frozen=True, slots=True)
class AdaptationBoundary:
    policy_revision: str
    allowed_parameters: frozenset[str]
    evidence: tuple[EvidenceRef, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        policy_revision: str,
        allowed_parameters: Iterable[str],
        evidence: Iterable[EvidenceRef],
    ) -> "AdaptationBoundary":
        revision = _nonempty(policy_revision, "policy_revision")
        allowed = frozenset(_canonical_parameter(row) for row in allowed_parameters)
        if not allowed:
            raise NeuralInvariantError("adaptation authority boundary must name at least one allowed parameter")
        if any(_is_protected_parameter(name) for name in allowed):
            raise NeuralInvariantError("adaptation authority boundary cannot include protected authority domains")
        ordered = _evidence_rows(evidence, "adaptation boundary evidence")
        digest = canonical_digest(
            {
                "policy_revision": revision,
                "allowed_parameters": sorted(allowed),
                "evidence": [row.to_state() for row in ordered],
            }
        )
        return cls(policy_revision=revision, allowed_parameters=allowed, evidence=ordered, digest=digest)

    def validate_update(self, update: Mapping[str, Any]) -> None:
        if not isinstance(update, Mapping) or not update:
            raise NeuralInvariantError("adaptation update must be a non-empty mapping")
        names = tuple(_canonical_parameter(name) for name in update)
        if any(_is_protected_parameter(name) for name in names):
            raise NeuralInvariantError("adaptation update crosses the Neural authority boundary")
        disallowed = sorted(set(names).difference(self.allowed_parameters))
        if disallowed:
            raise NeuralInvariantError(
                "adaptation update crosses the Neural authority boundary: " + ", ".join(disallowed)
            )


__all__ = (
    "AdaptationBoundary",
    "Candidate",
    "CandidateDecision",
    "CandidateRanker",
    "CognitiveState",
    "ConfidenceAssessment",
    "EvidenceRef",
    "ExpertRoute",
    "ExpertRouter",
    "RoutingDecision",
    "NeuralInvariantError",
    "NEURAL_CORE_REVISION",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
