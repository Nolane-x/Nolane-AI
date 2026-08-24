from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.events import EventLedger
from nolane.organization.identity import AgentRegistry


COMPONENT_ID = "external.experience"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.experience"


class ExperienceOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    MIXED = "mixed"


class LearningLayer(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    STRATEGY = "strategy"
    TOOL_USE = "tool_use"


@dataclass(frozen=True, slots=True)
class ExperienceRecord:
    experience_id: str
    agent_id: str
    region: str
    domain: str
    outcome: ExperienceOutcome
    summary: str
    task_id: str | None
    object_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "agent_id": self.agent_id,
            "region": self.region,
            "domain": self.domain,
            "outcome": self.outcome.value,
            "summary": self.summary,
            "task_id": self.task_id,
            "object_refs": list(self.object_refs),
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExperienceRecord":
        return cls(
            experience_id=str(state["experience_id"]),
            agent_id=str(state["agent_id"]),
            region=str(state["region"]),
            domain=str(state["domain"]),
            outcome=ExperienceOutcome(str(state["outcome"])),
            summary=str(state["summary"]),
            task_id=None if state.get("task_id") is None else str(state["task_id"]),
            object_refs=tuple(str(x) for x in state.get("object_refs", ())),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
        )


@dataclass(frozen=True, slots=True)
class AttributionRecord:
    attribution_id: str
    experience_id: str
    agent_id: str
    learning_layer: LearningLayer
    lesson: str
    positive: bool
    verifier_agent_id: str
    evidence: EvidenceRecord

    def to_state(self) -> dict[str, Any]:
        return {
            "attribution_id": self.attribution_id,
            "experience_id": self.experience_id,
            "agent_id": self.agent_id,
            "learning_layer": self.learning_layer.value,
            "lesson": self.lesson,
            "positive": self.positive,
            "verifier_agent_id": self.verifier_agent_id,
            "evidence": self.evidence.to_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AttributionRecord":
        return cls(
            attribution_id=str(state["attribution_id"]),
            experience_id=str(state["experience_id"]),
            agent_id=str(state["agent_id"]),
            learning_layer=LearningLayer(str(state["learning_layer"])),
            lesson=str(state["lesson"]),
            positive=bool(state["positive"]),
            verifier_agent_id=str(state["verifier_agent_id"]),
            evidence=EvidenceRecord.from_state(state["evidence"]),
        )


class ExperienceLedger:
    def __init__(self, *, registry: AgentRegistry, events: EventLedger) -> None:
        self.registry = registry
        self.events = events
        self._experiences: dict[str, ExperienceRecord] = {}
        self._attributions: dict[str, AttributionRecord] = {}

    def record(
        self,
        *,
        agent_id: str,
        author_agent_id: str,
        domain: str,
        outcome: ExperienceOutcome | str,
        summary: str,
        task_id: str | None = None,
        object_refs: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
    ) -> ExperienceRecord:
        identity = self.registry.get(agent_id)
        if str(author_agent_id) != identity.agent_id:
            raise PermissionError("permanent identities may only author their own experience records")
        domain = str(domain).strip()
        summary = str(summary).strip()
        if not domain or not summary:
            raise ValueError("experience domain and summary must be explicit")
        normalized = ExperienceOutcome(outcome)
        task = None if task_id is None else str(task_id)
        objects = tuple(str(x) for x in object_refs)
        evidence = tuple(str(x) for x in evidence_refs)
        digest_payload = {
            "agent_id": identity.agent_id,
            "region": identity.region,
            "domain": domain,
            "outcome": normalized.value,
            "summary": summary,
            "task_id": task,
            "object_refs": list(objects),
            "evidence_refs": list(evidence),
        }
        experience_id = "experience-" + canonical_digest(digest_payload)[:24]
        row = ExperienceRecord(
            experience_id=experience_id,
            agent_id=identity.agent_id,
            region=identity.region,
            domain=domain,
            outcome=normalized,
            summary=summary,
            task_id=task,
            object_refs=objects,
            evidence_refs=evidence,
        )
        existing = self._experiences.get(experience_id)
        if existing is not None:
            if existing != row:
                raise ValueError("experience id cannot be rebound")
            return existing
        self._experiences[experience_id] = row
        return row

    def get(self, experience_id: str) -> ExperienceRecord:
        try:
            return self._experiences[str(experience_id)]
        except KeyError as exc:
            raise KeyError(f"unknown experience id: {experience_id}") from exc

    def experiences_for(self, agent_id: str) -> tuple[ExperienceRecord, ...]:
        self.registry.get(agent_id)
        return tuple(
            sorted(
                (row for row in self._experiences.values() if row.agent_id == str(agent_id)),
                key=lambda row: row.experience_id,
            )
        )

    def attribute(
        self,
        experience_id: str,
        *,
        learning_layer: LearningLayer | str,
        lesson: str,
        evidence: EvidenceRecord,
    ) -> AttributionRecord:
        experience = self.get(experience_id)
        lesson = str(lesson).strip()
        if not lesson:
            raise ValueError("attribution lesson must be explicit")
        self.registry.get(evidence.verifier_agent_id)
        clean = evidence.passed and evidence.false_accepts == 0 and evidence.regressions == 0
        if clean and evidence.verifier_agent_id == experience.agent_id:
            raise PermissionError("positive learning attribution requires clean evidence external to the producer")
        positive = clean and evidence.verifier_agent_id != experience.agent_id
        layer = LearningLayer(learning_layer)
        payload = {
            "experience_id": experience.experience_id,
            "agent_id": experience.agent_id,
            "learning_layer": layer.value,
            "lesson": lesson,
            "positive": positive,
            "verifier_agent_id": evidence.verifier_agent_id,
            "evidence": evidence.to_state(),
        }
        attribution_id = "attribution-" + canonical_digest(payload)[:24]
        row = AttributionRecord(
            attribution_id=attribution_id,
            experience_id=experience.experience_id,
            agent_id=experience.agent_id,
            learning_layer=layer,
            lesson=lesson,
            positive=positive,
            verifier_agent_id=evidence.verifier_agent_id,
            evidence=evidence,
        )
        existing = self._attributions.get(attribution_id)
        if existing is not None:
            if existing != row:
                raise ValueError("attribution id cannot be rebound")
            return existing
        self._attributions[attribution_id] = row
        return row

    def get_attribution(self, attribution_id: str) -> AttributionRecord:
        try:
            return self._attributions[str(attribution_id)]
        except KeyError as exc:
            raise KeyError(f"unknown attribution id: {attribution_id}") from exc

    def attributions_for(self, agent_id: str) -> tuple[AttributionRecord, ...]:
        self.registry.get(agent_id)
        return tuple(
            sorted(
                (row for row in self._attributions.values() if row.agent_id == str(agent_id)),
                key=lambda row: row.attribution_id,
            )
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "experiences": [self._experiences[key].to_state() for key in sorted(self._experiences)],
            "attributions": [self._attributions[key].to_state() for key in sorted(self._attributions)],
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        events: EventLedger,
        state: Mapping[str, Any],
    ) -> "ExperienceLedger":
        ledger = cls(registry=registry, events=events)
        for raw in state.get("experiences", ()):
            row = ExperienceRecord.from_state(raw)
            registry.get(row.agent_id)
            ledger._experiences[row.experience_id] = row
        for raw in state.get("attributions", ()):
            row = AttributionRecord.from_state(raw)
            if row.experience_id not in ledger._experiences:
                raise ValueError("attribution references missing experience")
            ledger._attributions[row.attribution_id] = row
        return ledger


__all__ = (
    "ExperienceOutcome",
    "LearningLayer",
    "ExperienceRecord",
    "AttributionRecord",
    "ExperienceLedger",
)
