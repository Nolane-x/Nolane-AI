from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping

from nolane.schemas.identity import AgentIdentity, AgentStatus

COMPONENT_ID = "organization.identity"
COMPONENT_VERSION = "0.0.4"
MIGRATED_FROM = "cogcoder.organization.registry"

_EXECUTION_AUTHORITY_REVOKING_STATUSES = frozenset(
    (AgentStatus.SLEEPING, AgentStatus.PAUSED)
)
_AUTHORITY_REVISION_FIELDS = frozenset(("execution", "neural_version", "self_model"))


def _authority_revision_value(value: Any, *, field: str, agent_id: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(
            f"identity authority revision {field} for {agent_id} must be a non-negative integer"
        )
    return value


class AgentRegistry:
    """Canonical permanent-agent registry.

    Wave 2 moves implementation ownership here while preserving the accepted
    state and mutation contract exactly. Historical imports bridge back to this
    class so permanent identity behavior has one implementation authority.
    """

    def __init__(self, identities: Iterable[AgentIdentity] = ()) -> None:
        self._rows: dict[str, AgentIdentity] = {}
        self._accepted_versions: dict[str, list[str]] = {}
        self._execution_authority_revisions: dict[str, int] = {}
        self._neural_version_authority_revisions: dict[str, int] = {}
        self._self_model_authority_revisions: dict[str, int] = {}
        for identity in identities:
            self.register(identity)

    def register(self, identity: AgentIdentity) -> None:
        if identity.agent_id in self._rows:
            raise ValueError(f"duplicate agent id: {identity.agent_id}")
        self._rows[identity.agent_id] = identity
        self._accepted_versions[identity.agent_id] = [identity.neural_version]
        self._execution_authority_revisions[identity.agent_id] = 0
        self._neural_version_authority_revisions[identity.agent_id] = 0
        self._self_model_authority_revisions[identity.agent_id] = 0

    def get(self, agent_id: str) -> AgentIdentity:
        try:
            return self._rows[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f"unknown agent id: {agent_id}") from exc

    def identities(self) -> tuple[AgentIdentity, ...]:
        return tuple(self._rows.values())

    def set_status(self, agent_id: str, status: AgentStatus) -> AgentIdentity:
        old = self.get(agent_id)
        next_status = AgentStatus(status)
        row = replace(old, status=next_status)
        if (
            old.status != next_status
            and next_status in _EXECUTION_AUTHORITY_REVOKING_STATUSES
        ):
            self._execution_authority_revisions[row.agent_id] += 1
        self._rows[row.agent_id] = row
        return row

    def execution_authority_revision(self, agent_id: str) -> int:
        agent_key = str(agent_id)
        self.get(agent_key)
        return self._execution_authority_revisions[agent_key]

    def neural_version_authority_revision(self, agent_id: str) -> int:
        agent_key = str(agent_id)
        self.get(agent_key)
        return self._neural_version_authority_revisions[agent_key]

    def self_model_authority_revision(self, agent_id: str) -> int:
        agent_key = str(agent_id)
        self.get(agent_key)
        return self._self_model_authority_revisions[agent_key]

    def bind_task(self, agent_id: str, task_id: str | None) -> AgentIdentity:
        old = self.get(agent_id)
        row = replace(old, current_task=None if task_id is None else str(task_id))
        self._rows[row.agent_id] = row
        return row

    def set_checkpoint(self, agent_id: str, checkpoint_id: str | None) -> AgentIdentity:
        old = self.get(agent_id)
        row = replace(old, checkpoint_id=None if checkpoint_id is None else str(checkpoint_id))
        self._rows[row.agent_id] = row
        return row

    def set_self_model_version(self, agent_id: str, self_model_version: str) -> AgentIdentity:
        version = str(self_model_version).strip()
        if not version:
            raise ValueError("self-model version must be non-empty")
        old = self.get(agent_id)
        row = replace(old, self_model_version=version)
        if old.self_model_version != version:
            self._self_model_authority_revisions[row.agent_id] += 1
        self._rows[row.agent_id] = row
        return row

    def accept_neural_version(self, agent_id: str, neural_version: str) -> AgentIdentity:
        version = str(neural_version).strip()
        if not version:
            raise ValueError("accepted neural version must be non-empty")
        old = self.get(agent_id)
        row = replace(old, neural_version=version)
        if old.neural_version != version:
            self._neural_version_authority_revisions[row.agent_id] += 1
        self._rows[row.agent_id] = row
        history = self._accepted_versions.setdefault(row.agent_id, [])
        if version not in history:
            history.append(version)
        return row

    def accepted_versions(self, agent_id: str) -> tuple[str, ...]:
        self.get(agent_id)
        return tuple(self._accepted_versions[agent_id])

    def to_state(self) -> dict[str, Any]:
        return {
            "identities": [row.to_state() for row in self.identities()],
            "accepted_versions": {key: list(value) for key, value in sorted(self._accepted_versions.items())},
            "authority_revisions": {
                agent_id: {
                    "execution": self._execution_authority_revisions[agent_id],
                    "neural_version": self._neural_version_authority_revisions[agent_id],
                    "self_model": self._self_model_authority_revisions[agent_id],
                }
                for agent_id in sorted(self._rows)
            },
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AgentRegistry":
        registry = cls(AgentIdentity.from_state(row) for row in state.get("identities", ()))
        accepted = state.get("accepted_versions", {})
        if isinstance(accepted, Mapping):
            for agent_id, versions in accepted.items():
                registry.get(str(agent_id))
                history = [str(version) for version in versions]
                current = registry.get(str(agent_id)).neural_version
                if current not in history:
                    history.append(current)
                registry._accepted_versions[str(agent_id)] = history

        # Absence is the explicit compatibility contract for pre-authority-clock
        # snapshots. Once the field is present it is canonical state and must be
        # complete, exact and type-safe before any restored clock is admitted.
        if "authority_revisions" not in state:
            return registry

        revisions = state["authority_revisions"]
        if not isinstance(revisions, Mapping):
            raise ValueError("identity authority revisions state must be a mapping")
        if any(type(agent_id) is not str for agent_id in revisions):
            raise ValueError("identity authority revision agent ids must be strings")

        expected_agent_ids = set(registry._rows)
        actual_agent_ids = set(revisions)
        if actual_agent_ids != expected_agent_ids:
            missing = sorted(expected_agent_ids - actual_agent_ids)
            unknown = sorted(actual_agent_ids - expected_agent_ids)
            raise ValueError(
                "identity authority revision agent set mismatch: "
                f"missing={missing}, unknown={unknown}"
            )

        parsed: dict[str, tuple[int, int, int]] = {}
        for agent_id in sorted(expected_agent_ids):
            row = revisions[agent_id]
            if not isinstance(row, Mapping):
                raise ValueError("identity authority revision row must be a mapping")
            if any(type(field) is not str for field in row):
                raise ValueError("identity authority revision field names must be strings")
            actual_fields = set(row)
            if actual_fields != _AUTHORITY_REVISION_FIELDS:
                missing = sorted(_AUTHORITY_REVISION_FIELDS - actual_fields)
                unknown = sorted(actual_fields - _AUTHORITY_REVISION_FIELDS)
                raise ValueError(
                    f"identity authority revision fields for {agent_id} mismatch: "
                    f"missing={missing}, unknown={unknown}"
                )
            parsed[agent_id] = (
                _authority_revision_value(row["execution"], field="execution", agent_id=agent_id),
                _authority_revision_value(
                    row["neural_version"], field="neural_version", agent_id=agent_id
                ),
                _authority_revision_value(
                    row["self_model"], field="self_model", agent_id=agent_id
                ),
            )

        # Commit only after the complete snapshot validates, so no malformed
        # later row can leave a partially restored authority generation.
        registry._execution_authority_revisions = {
            agent_id: values[0] for agent_id, values in parsed.items()
        }
        registry._neural_version_authority_revisions = {
            agent_id: values[1] for agent_id, values in parsed.items()
        }
        registry._self_model_authority_revisions = {
            agent_id: values[2] for agent_id, values in parsed.items()
        }
        return registry


__all__ = (
    "AgentRegistry",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
