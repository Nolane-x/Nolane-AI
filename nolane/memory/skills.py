from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord


COMPONENT_ID = "external.skills"
COMPONENT_VERSION = "0.0.3"
MIGRATED_FROM = "cogcoder.organization.evolution"


class SkillScope(str, Enum):
    CANDIDATE = "candidate"
    PERSONAL = "personal"
    REGIONAL = "regional"
    GLOBAL = "global"


@dataclass(frozen=True, slots=True)
class SkillRecord:
    skill_id: str
    owner_agent_id: str
    region: str
    name: str
    body: str
    content_digest: str
    scope: SkillScope = SkillScope.CANDIDATE
    evidence: tuple[EvidenceRecord, ...] = ()
    quarantined: bool = False
    quarantine_reason: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "owner_agent_id": self.owner_agent_id,
            "region": self.region,
            "name": self.name,
            "body": self.body,
            "content_digest": self.content_digest,
            "scope": self.scope.value,
            "evidence": [row.to_state() for row in self.evidence],
            "quarantined": self.quarantined,
            "quarantine_reason": self.quarantine_reason,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SkillRecord":
        return cls(
            skill_id=str(state["skill_id"]),
            owner_agent_id=str(state["owner_agent_id"]),
            region=str(state["region"]),
            name=str(state["name"]),
            body=str(state["body"]),
            content_digest=str(state["content_digest"]),
            scope=SkillScope(str(state.get("scope", SkillScope.CANDIDATE.value))),
            evidence=tuple(EvidenceRecord.from_state(row) for row in state.get("evidence", ())),
            quarantined=bool(state.get("quarantined", False)),
            quarantine_reason=None if state.get("quarantine_reason") is None else str(state["quarantine_reason"]),
        )


class SkillEvolutionEngine:
    _REQUIRED_VERIFIERS = {
        SkillScope.PERSONAL: 1,
        SkillScope.REGIONAL: 2,
        SkillScope.GLOBAL: 3,
    }

    def __init__(self) -> None:
        self._skills: dict[str, SkillRecord] = {}

    def propose(self, *, owner_agent_id: str, region: str, name: str, body: str) -> SkillRecord:
        if not all(str(value).strip() for value in (owner_agent_id, region, name, body)):
            raise ValueError("skill owner, region, name and body must be explicit")
        digest = canonical_digest(
            {
                "owner_agent_id": str(owner_agent_id),
                "region": str(region),
                "name": str(name),
                "body": str(body),
            }
        )
        skill_id = "skill-" + digest[:20]
        existing = self._skills.get(skill_id)
        if existing is not None:
            return existing
        row = SkillRecord(
            skill_id=skill_id,
            owner_agent_id=str(owner_agent_id),
            region=str(region),
            name=str(name),
            body=str(body),
            content_digest=digest,
        )
        self._skills[row.skill_id] = row
        return row

    def get(self, skill_id: str) -> SkillRecord:
        try:
            return self._skills[str(skill_id)]
        except KeyError as exc:
            raise KeyError(f"unknown skill id: {skill_id}") from exc

    def verify(self, skill_id: str, evidence: EvidenceRecord) -> SkillRecord:
        old = self.get(skill_id)
        by_id = {row.evidence_id: row for row in old.evidence}
        existing = by_id.get(evidence.evidence_id)
        if existing is not None and existing != evidence:
            raise ValueError("evidence id cannot be rebound to different evidence")
        by_id[evidence.evidence_id] = evidence
        row = replace(old, evidence=tuple(by_id[key] for key in sorted(by_id)))
        self._skills[row.skill_id] = row
        return row

    @staticmethod
    def _valid_verifiers(skill: SkillRecord) -> set[str]:
        return {
            row.verifier_agent_id
            for row in skill.evidence
            if row.passed and row.false_accepts == 0 and row.regressions == 0
        }

    def promote(self, skill_id: str, scope: SkillScope) -> SkillRecord:
        old = self.get(skill_id)
        scope = SkillScope(scope)
        if old.quarantined:
            raise PermissionError("quarantined skill cannot be promoted")
        if scope is SkillScope.CANDIDATE:
            raise ValueError("candidate is not a promotion target")
        required = self._REQUIRED_VERIFIERS[scope]
        if len(self._valid_verifiers(old)) < required:
            raise PermissionError(f"{scope.value} promotion requires {required} independent valid verifier(s)")
        order = {
            SkillScope.CANDIDATE: 0,
            SkillScope.PERSONAL: 1,
            SkillScope.REGIONAL: 2,
            SkillScope.GLOBAL: 3,
        }
        if order[scope] < order[old.scope]:
            raise ValueError("skill promotion cannot silently demote scope")
        row = replace(old, scope=scope)
        self._skills[row.skill_id] = row
        return row

    def quarantine(self, skill_id: str, *, reason: str) -> SkillRecord:
        old = self.get(skill_id)
        if not str(reason).strip():
            raise ValueError("quarantine reason must be explicit")
        row = replace(old, quarantined=True, quarantine_reason=str(reason))
        self._skills[row.skill_id] = row
        return row

    def skills_for(self, agent_id: str, *, region: str) -> tuple[SkillRecord, ...]:
        rows: list[SkillRecord] = []
        for row in self._skills.values():
            if row.quarantined or row.scope is SkillScope.CANDIDATE:
                continue
            if row.scope is SkillScope.GLOBAL:
                rows.append(row)
            elif row.scope is SkillScope.REGIONAL and row.region == str(region):
                rows.append(row)
            elif row.scope is SkillScope.PERSONAL and row.owner_agent_id == str(agent_id):
                rows.append(row)
        return tuple(sorted(rows, key=lambda item: item.skill_id))

    def to_state(self) -> dict[str, Any]:
        return {"skills": [self._skills[key].to_state() for key in sorted(self._skills)]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SkillEvolutionEngine":
        engine = cls()
        seen_skill_ids: set[str] = set()
        for value in state.get("skills", ()):
            row = SkillRecord.from_state(value)
            if row.skill_id in seen_skill_ids:
                raise ValueError("duplicate serialized skill id")
            seen_skill_ids.add(row.skill_id)

            evidence_ids = [evidence.evidence_id for evidence in row.evidence]
            if len(set(evidence_ids)) != len(evidence_ids):
                raise ValueError("duplicate serialized skill evidence id")

            canonical = engine.propose(
                owner_agent_id=row.owner_agent_id,
                region=row.region,
                name=row.name,
                body=row.body,
            )
            if canonical.skill_id != row.skill_id or canonical.content_digest != row.content_digest:
                raise ValueError("skill restore content digest or skill id is not canonical")

            for evidence in row.evidence:
                engine.verify(row.skill_id, evidence)
            if row.scope is not SkillScope.CANDIDATE:
                engine.promote(row.skill_id, row.scope)
            if row.quarantined:
                engine.quarantine(row.skill_id, reason=row.quarantine_reason or "")
            elif row.quarantine_reason is not None:
                raise ValueError("skill quarantine reason requires quarantined state")

            if engine.get(row.skill_id) != row:
                raise ValueError("skill restore is not canonical")
        return engine


__all__ = ("SkillScope", "SkillRecord", "SkillEvolutionEngine")
