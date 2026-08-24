from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry

COMPONENT_ID = "external.self_model"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.self_model"


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
    def __init__(self, registry: AgentRegistry, *, initialize: bool = True) -> None:
        self.registry = registry
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

    def update_competence(
        self,
        agent_id: str,
        *,
        domain: str,
        score: float,
        evidence: EvidenceRecord,
    ) -> SelfModel:
        self._require_external_valid_evidence(agent_id, evidence)
        if not 0.0 <= float(score) <= 1.0:
            raise ValueError("competence score must lie in [0, 1]")
        if not str(domain).strip():
            raise ValueError("competence domain must be explicit")
        old = self.get(agent_id)
        values = dict(old.domain_competence)
        values[str(domain)] = float(score)
        revision = self._revisions.get(str(agent_id), 1) + 1
        self._revisions[str(agent_id)] = revision
        row = replace(
            old,
            version=f"self-model-{revision:08d}",
            domain_competence=tuple(sorted(values.items())),
            evidence_ids=tuple(dict.fromkeys(old.evidence_ids + (evidence.evidence_id,))),
        )
        self._models[row.agent_id] = row
        if hasattr(self.registry, "set_self_model_version"):
            self.registry.set_self_model_version(row.agent_id, row.version)
        return row

    def to_state(self) -> dict[str, Any]:
        return {
            "models": [self._models[key].to_state() for key in sorted(self._models)],
            "revisions": dict(sorted(self._revisions.items())),
        }

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> "SelfModelRegistry":
        result = cls(registry, initialize=False)
        for value in state.get("models", ()):
            row = SelfModel.from_state(value)
            result._models[row.agent_id] = row
        result._revisions = {str(k): int(v) for k, v in state.get("revisions", {}).items()}
        for identity in registry.identities():
            if identity.agent_id not in result._models:
                version = getattr(identity, "self_model_version", "self-model-0.1")
                result._models[identity.agent_id] = SelfModel(identity.agent_id, str(version))
                result._revisions[identity.agent_id] = 1
        return result


__all__ = ["SelfModel", "SelfModelRegistry"]
