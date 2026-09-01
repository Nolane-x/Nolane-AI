from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.learning_authority import LearningEvidenceAuthority
from nolane.organization.identity import AgentRegistry

COMPONENT_ID = "external.self_model"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.organization.self_model"

_COMMITTED_VERSION = re.compile(r"^self-model-(\d{8})$")


def _committed_revision(version: str) -> int | None:
    match = _COMMITTED_VERSION.fullmatch(str(version))
    if match is None:
        return None
    revision = int(match.group(1))
    if revision <= 0:
        raise ValueError("committed self-model revision must be positive")
    return revision


@dataclass(frozen=True, slots=True)
class SelfModel:
    agent_id: str
    version: str
    domain_competence: tuple[tuple[str, float], ...] = ()
    tool_competence: tuple[tuple[str, float], ...] = ()
    failure_modes: tuple[str, ...] = ()
    calibration: float = 0.5
    trusted_skill_ids: tuple[str, ...] = ()
    blind_spots: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.agent_id).strip() or not str(self.version).strip():
            raise ValueError("self-model identity and version must be explicit")
        if not 0.0 <= float(self.calibration) <= 1.0:
            raise ValueError("self-model calibration must lie in [0, 1]")
        for label, rows in (
            ("domain competence", self.domain_competence),
            ("tool competence", self.tool_competence),
        ):
            seen: set[str] = set()
            for key, value in rows:
                normalized = str(key).strip()
                if not normalized:
                    raise ValueError(f"{label} key must be explicit")
                if normalized in seen:
                    raise ValueError(f"duplicate {label} key: {normalized}")
                if not 0.0 <= float(value) <= 1.0:
                    raise ValueError(f"{label} score must lie in [0, 1]")
                seen.add(normalized)

    def to_state(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "domain_competence": [[key, value] for key, value in self.domain_competence],
            "tool_competence": [[key, value] for key, value in self.tool_competence],
            "failure_modes": list(self.failure_modes),
            "calibration": self.calibration,
            "trusted_skill_ids": list(self.trusted_skill_ids),
            "blind_spots": list(self.blind_spots),
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SelfModel":
        return cls(
            agent_id=str(state["agent_id"]),
            version=str(state["version"]),
            domain_competence=tuple((str(k), float(v)) for k, v in state.get("domain_competence", ())),
            tool_competence=tuple((str(k), float(v)) for k, v in state.get("tool_competence", ())),
            failure_modes=tuple(str(x) for x in state.get("failure_modes", ())),
            calibration=float(state.get("calibration", 0.5)),
            trusted_skill_ids=tuple(str(x) for x in state.get("trusted_skill_ids", ())),
            blind_spots=tuple(str(x) for x in state.get("blind_spots", ())),
            evidence_ids=tuple(str(x) for x in state.get("evidence_ids", ())),
        )


class SelfModelRegistry:
    def __init__(
        self,
        registry: AgentRegistry,
        *,
        initialize: bool = True,
        learning_authority: LearningEvidenceAuthority | None = None,
    ) -> None:
        self.registry = registry
        self.learning_authority = learning_authority
        self._models: dict[str, SelfModel] = {}
        self._revisions: dict[str, int] = {}
        if initialize:
            for identity in registry.identities():
                version = getattr(identity, "self_model_version", "self-model-0.1")
                self._models[identity.agent_id] = SelfModel(identity.agent_id, str(version))
                self._revisions[identity.agent_id] = 1

    def get(self, agent_id: str) -> SelfModel:
        self.registry.get(agent_id)
        try:
            return self._models[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f"missing self model for {agent_id}") from exc

    @staticmethod
    def _require_external_valid_evidence(agent_id: str, evidence: EvidenceRecord) -> None:
        if not evidence.passed or evidence.false_accepts or evidence.regressions:
            raise PermissionError("self-model improvement requires passing evidence without regressions or false accepts")
        if evidence.verifier_agent_id == str(agent_id):
            raise PermissionError("self-model improvement requires evidence external to the producer")

    def _mutation_subject_digest(
        self,
        agent_id: str,
        *,
        operation_class: str,
        proposed_change: Mapping[str, Any],
    ) -> str:
        return canonical_digest(
            {
                "current_self_model": self.get(agent_id).to_state(),
                "operation_class": str(operation_class),
                "proposed_change": dict(proposed_change),
            }
        )

    def competence_subject_digest(self, agent_id: str, *, domain: str, score: float) -> str:
        normalized_domain = str(domain).strip()
        if not normalized_domain:
            raise ValueError("competence domain must be explicit")
        value = float(score)
        if not 0.0 <= value <= 1.0:
            raise ValueError("competence score must lie in [0, 1]")
        return self._mutation_subject_digest(
            agent_id,
            operation_class="self_model.update_competence",
            proposed_change={"domain": normalized_domain, "score": value},
        )

    def _authorize_mutation(
        self,
        agent_id: str,
        *,
        operation_class: str,
        evidence: EvidenceRecord,
        subject_digest: str,
        authority_lease_id: str | None,
        use_ref: str,
    ) -> None:
        authority = self.learning_authority
        if authority is None:
            return
        if authority_lease_id is None or not str(authority_lease_id).strip():
            raise PermissionError("self-model improvement requires a preissued learning evidence lease")
        authority.consume(
            str(authority_lease_id),
            subject_kind="self_model",
            subject_id=str(agent_id),
            operation_class=operation_class,
            producer_agent_id=str(agent_id),
            evidence=evidence,
            subject_digest=subject_digest,
            use_ref=f"self-model:{agent_id}:{use_ref}",
        )

    def _next_version(self, agent_id: str) -> str:
        revision = self._revisions.get(str(agent_id), 1) + 1
        return f"self-model-{revision:08d}"

    def _commit(self, agent_id: str, evidence: EvidenceRecord, **changes: Any) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        old = self.get(agent_id)
        revision = self._revisions.get(str(agent_id), 1) + 1
        self._revisions[str(agent_id)] = revision
        row = replace(
            old,
            version=f"self-model-{revision:08d}",
            evidence_ids=tuple(dict.fromkeys(old.evidence_ids + (evidence.evidence_id,))),
            **changes,
        )
        self._models[row.agent_id] = row
        if hasattr(self.registry, "set_self_model_version"):
            self.registry.set_self_model_version(row.agent_id, row.version)
        return row

    def update_competence(
        self,
        agent_id: str,
        *,
        domain: str,
        score: float,
        evidence: EvidenceRecord,
        authority_lease_id: str | None = None,
    ) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        value = float(score)
        if not 0.0 <= value <= 1.0:
            raise ValueError("competence score must lie in [0, 1]")
        domain = str(domain).strip()
        if not domain:
            raise ValueError("competence domain must be explicit")
        digest = self.competence_subject_digest(agent_id, domain=domain, score=value)
        next_version = self._next_version(agent_id)
        self._authorize_mutation(
            agent_id,
            operation_class="self_model.update_competence",
            evidence=evidence,
            subject_digest=digest,
            authority_lease_id=authority_lease_id,
            use_ref=next_version,
        )
        values = dict(self.get(agent_id).domain_competence)
        values[domain] = value
        return self._commit(agent_id, evidence, domain_competence=tuple(sorted(values.items())))

    def update_tool_competence(
        self,
        agent_id: str,
        *,
        tool: str,
        score: float,
        evidence: EvidenceRecord,
        authority_lease_id: str | None = None,
    ) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        value = float(score)
        if not 0.0 <= value <= 1.0:
            raise ValueError("tool competence score must lie in [0, 1]")
        tool = str(tool).strip()
        if not tool:
            raise ValueError("tool identity must be explicit")
        digest = self._mutation_subject_digest(
            agent_id,
            operation_class="self_model.update_tool_competence",
            proposed_change={"tool": tool, "score": value},
        )
        self._authorize_mutation(
            agent_id,
            operation_class="self_model.update_tool_competence",
            evidence=evidence,
            subject_digest=digest,
            authority_lease_id=authority_lease_id,
            use_ref=self._next_version(agent_id),
        )
        values = dict(self.get(agent_id).tool_competence)
        values[tool] = value
        return self._commit(agent_id, evidence, tool_competence=tuple(sorted(values.items())))

    def record_failure_mode(
        self,
        agent_id: str,
        *,
        failure_mode: str,
        evidence: EvidenceRecord,
        authority_lease_id: str | None = None,
    ) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        value = str(failure_mode).strip()
        if not value:
            raise ValueError("failure mode must be explicit")
        old = self.get(agent_id)
        digest = self._mutation_subject_digest(
            agent_id,
            operation_class="self_model.record_failure_mode",
            proposed_change={"failure_mode": value},
        )
        self._authorize_mutation(
            agent_id,
            operation_class="self_model.record_failure_mode",
            evidence=evidence,
            subject_digest=digest,
            authority_lease_id=authority_lease_id,
            use_ref=self._next_version(agent_id),
        )
        return self._commit(agent_id, evidence, failure_modes=tuple(dict.fromkeys(old.failure_modes + (value,))))

    def record_blind_spot(
        self,
        agent_id: str,
        *,
        blind_spot: str,
        evidence: EvidenceRecord,
        authority_lease_id: str | None = None,
    ) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        value = str(blind_spot).strip()
        if not value:
            raise ValueError("blind spot must be explicit")
        old = self.get(agent_id)
        digest = self._mutation_subject_digest(
            agent_id,
            operation_class="self_model.record_blind_spot",
            proposed_change={"blind_spot": value},
        )
        self._authorize_mutation(
            agent_id,
            operation_class="self_model.record_blind_spot",
            evidence=evidence,
            subject_digest=digest,
            authority_lease_id=authority_lease_id,
            use_ref=self._next_version(agent_id),
        )
        return self._commit(agent_id, evidence, blind_spots=tuple(dict.fromkeys(old.blind_spots + (value,))))

    def update_calibration(
        self,
        agent_id: str,
        *,
        calibration: float,
        evidence: EvidenceRecord,
        authority_lease_id: str | None = None,
    ) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        value = float(calibration)
        if not 0.0 <= value <= 1.0:
            raise ValueError("self-model calibration must lie in [0, 1]")
        digest = self._mutation_subject_digest(
            agent_id,
            operation_class="self_model.update_calibration",
            proposed_change={"calibration": value},
        )
        self._authorize_mutation(
            agent_id,
            operation_class="self_model.update_calibration",
            evidence=evidence,
            subject_digest=digest,
            authority_lease_id=authority_lease_id,
            use_ref=self._next_version(agent_id),
        )
        return self._commit(agent_id, evidence, calibration=value)

    def trust_skill(
        self,
        agent_id: str,
        *,
        skill_id: str,
        evidence: EvidenceRecord,
        authority_lease_id: str | None = None,
    ) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        value = str(skill_id).strip()
        if not value:
            raise ValueError("trusted skill id must be explicit")
        old = self.get(agent_id)
        digest = self._mutation_subject_digest(
            agent_id,
            operation_class="self_model.trust_skill",
            proposed_change={"skill_id": value},
        )
        self._authorize_mutation(
            agent_id,
            operation_class="self_model.trust_skill",
            evidence=evidence,
            subject_digest=digest,
            authority_lease_id=authority_lease_id,
            use_ref=self._next_version(agent_id),
        )
        return self._commit(agent_id, evidence, trusted_skill_ids=tuple(dict.fromkeys(old.trusted_skill_ids + (value,))))

    def to_state(self) -> dict[str, Any]:
        return {
            "models": [self._models[key].to_state() for key in sorted(self._models)],
            "revisions": dict(sorted(self._revisions.items())),
        }

    @classmethod
    def from_state(
        cls,
        registry: AgentRegistry,
        state: Mapping[str, Any],
        *,
        learning_authority: LearningEvidenceAuthority | None = None,
    ) -> "SelfModelRegistry":
        result = cls(registry, initialize=False, learning_authority=learning_authority)
        seen: set[str] = set()
        for value in state.get("models", ()):
            row = SelfModel.from_state(value)
            registry.get(row.agent_id)
            if row.agent_id in seen:
                raise ValueError(f"duplicate self-model agent row: {row.agent_id}")
            seen.add(row.agent_id)
            result._models[row.agent_id] = row

        revisions: dict[str, int] = {}
        for key, value in state.get("revisions", {}).items():
            agent_id = str(key)
            registry.get(agent_id)
            revision = int(value)
            if revision <= 0:
                raise ValueError("self-model revision must be positive")
            revisions[agent_id] = revision
        result._revisions = revisions

        for agent_id, row in result._models.items():
            committed_revision = _committed_revision(row.version)
            revision = result._revisions.get(agent_id)
            if committed_revision is not None:
                if revision != committed_revision:
                    raise ValueError(
                        f"self-model revision mismatch for {agent_id}: "
                        f"version commits {committed_revision}, ledger has {revision}"
                    )
            elif revision is None:
                result._revisions[agent_id] = 1

        for identity in registry.identities():
            if identity.agent_id not in result._models:
                dangling_revision = result._revisions.get(identity.agent_id)
                if dangling_revision not in (None, 1):
                    raise ValueError(
                        f"self-model revision {dangling_revision} for {identity.agent_id} has no committed model row"
                    )
                version = getattr(identity, "self_model_version", "self-model-0.1")
                result._models[identity.agent_id] = SelfModel(identity.agent_id, str(version))
                result._revisions[identity.agent_id] = 1

        unknown_revision_agents = set(result._revisions).difference(result._models)
        if unknown_revision_agents:
            raise ValueError("self-model revision ledger contains agents without model rows")

        if hasattr(registry, "set_self_model_version"):
            for agent_id in sorted(result._models):
                registry.set_self_model_version(agent_id, result._models[agent_id].version)
        return result


__all__ = ["SelfModel", "SelfModelRegistry"]
