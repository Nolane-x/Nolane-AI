from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .identity import AgentRegistry

COMPONENT_ID = "organization.authority"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.authority"


def _canonical_state_record(
    state: object,
    expected_keys: tuple[str, ...],
    label: str,
) -> dict[str, Any]:
    if type(state) is not dict or set(state) != set(expected_keys):
        raise ValueError(f"{label} must use canonical serialized state")
    return state


def _canonical_state_list(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{label} must use a canonical serialized list")
    return value


def _exact_string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} must be an exact string")
    return value


def _non_empty_string(value: object, label: str) -> str:
    text = _exact_string(value, label)
    if not text.strip():
        raise ValueError(f"{label} must be non-empty")
    return text


def _non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative exact integer")
    return value


def _sequence_number(value: object, prefix: str, label: str) -> int:
    identity = _exact_string(value, label)
    if not identity.startswith(prefix):
        raise ValueError(f"{label} is not canonical")
    suffix = identity[len(prefix):]
    if not suffix.isdigit():
        raise ValueError(f"{label} is not canonical")
    number = int(suffix)
    if number <= 0 or identity != f"{prefix}{number:08d}":
        raise ValueError(f"{label} is not canonical")
    return number


def _validate_sequence_counter(numbers: list[int], counter: int, label: str) -> None:
    if len(numbers) != counter:
        raise ValueError(f"{label} counter does not match canonical authority lineage")
    for expected, actual in enumerate(sorted(numbers), start=1):
        if actual != expected:
            raise ValueError(f"{label} counter does not match canonical authority lineage")


@dataclass(frozen=True, slots=True)
class AuthorityBlock:
    block_id: str
    artifact_id: str
    blocker_agent_id: str
    reason: str

    def to_state(self) -> dict[str, str]:
        return {
            "block_id": self.block_id,
            "artifact_id": self.artifact_id,
            "blocker_agent_id": self.blocker_agent_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OverrideReceipt:
    override_id: str
    artifact_id: str
    actor_agent_id: str
    reason: str
    evidence_ids: tuple[str, ...]
    overrode_block: bool

    def to_state(self) -> dict[str, Any]:
        return {
            "override_id": self.override_id,
            "artifact_id": self.artifact_id,
            "actor_agent_id": self.actor_agent_id,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "overrode_block": self.overrode_block,
        }


class AuthorityGraph:
    """Canonical write-ownership and fail-closed block authority graph."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self._owners: dict[str, str] = {}
        self._blocks: dict[str, list[AuthorityBlock]] = {}
        self._overrides: dict[str, OverrideReceipt] = {}
        self._block_counter = 0
        self._override_counter = 0

    def claim_owner(self, artifact_id: str, owner_agent_id: str) -> None:
        artifact = str(artifact_id).strip()
        if not artifact:
            raise ValueError("artifact id must be non-empty")
        self.registry.get(owner_agent_id)
        existing = self._owners.get(artifact)
        if existing is not None and existing != owner_agent_id:
            raise ValueError(f"artifact {artifact} already owned by {existing}")
        self._owners[artifact] = str(owner_agent_id)

    def owner_of(self, artifact_id: str) -> str | None:
        return self._owners.get(str(artifact_id))

    def record_block(self, artifact_id: str, blocker_agent_id: str, *, reason: str) -> AuthorityBlock:
        self.registry.get(blocker_agent_id)
        if not str(reason).strip():
            raise ValueError("block reason must be explicit")
        self._block_counter += 1
        row = AuthorityBlock(
            block_id=f"block-{self._block_counter:08d}",
            artifact_id=str(artifact_id),
            blocker_agent_id=str(blocker_agent_id),
            reason=str(reason),
        )
        self._blocks.setdefault(row.artifact_id, []).append(row)
        return row

    def blocks_for(self, artifact_id: str) -> tuple[AuthorityBlock, ...]:
        return tuple(self._blocks.get(str(artifact_id), ()))

    def central_override(self, *, artifact_id: str, reason: str, evidence_ids: tuple[str, ...]) -> OverrideReceipt:
        self.registry.get("nolane.central")
        if not str(reason).strip():
            raise ValueError("Central override requires an explicit reason")
        if not evidence_ids:
            raise ValueError("Central override requires explicit evidence ids")
        self._override_counter += 1
        row = OverrideReceipt(
            override_id=f"override-{self._override_counter:08d}",
            artifact_id=str(artifact_id),
            actor_agent_id="nolane.central",
            reason=str(reason),
            evidence_ids=tuple(str(value) for value in evidence_ids),
            overrode_block=bool(self._blocks.get(str(artifact_id))),
        )
        self._overrides[row.override_id] = row
        return row

    def can_write(self, actor_agent_id: str, artifact_id: str, *, override_id: str | None = None) -> bool:
        actor = self.registry.get(actor_agent_id)
        artifact = str(artifact_id)
        blocked = bool(self._blocks.get(artifact))
        if override_id is not None:
            receipt = self._overrides.get(str(override_id))
            return bool(
                receipt
                and receipt.actor_agent_id == actor.agent_id
                and receipt.artifact_id == artifact
                and actor.agent_id == "nolane.central"
            )
        if blocked:
            return False
        if actor.agent_id == "nolane.central":
            return True
        return self._owners.get(artifact) == actor.agent_id

    def require_write(self, actor_agent_id: str, artifact_id: str, *, override_id: str | None = None) -> None:
        if self.can_write(actor_agent_id, artifact_id, override_id=override_id):
            return
        if self._blocks.get(str(artifact_id)):
            raise PermissionError(f"artifact {artifact_id} is blocked by independent authority")
        raise PermissionError(f"agent {actor_agent_id} is not authorized to write artifact {artifact_id}")

    def to_state(self) -> dict[str, Any]:
        return {
            "owners": dict(sorted(self._owners.items())),
            "blocks": {
                key: [row.to_state() for row in value]
                for key, value in sorted(self._blocks.items())
            },
            "overrides": {
                key: value.to_state()
                for key, value in sorted(self._overrides.items())
            },
            "block_counter": self._block_counter,
            "override_counter": self._override_counter,
        }

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> "AuthorityGraph":
        serialized = _canonical_state_record(
            state,
            ("owners", "blocks", "overrides", "block_counter", "override_counter"),
            "authority graph",
        )

        owners_state = _canonical_state_record(serialized["owners"], (), "authority owners") if not serialized["owners"] else serialized["owners"]
        if type(owners_state) is not dict:
            raise ValueError("authority owners must use canonical serialized state")
        owners: dict[str, str] = {}
        for artifact_id, owner_agent_id in owners_state.items():
            artifact = _non_empty_string(artifact_id, "authority owner artifact identity")
            owner = _exact_string(owner_agent_id, "authority owner agent identity")
            try:
                registry.get(owner)
            except KeyError as exc:
                raise ValueError("authority owner agent identity is unknown") from exc
            owners[artifact] = owner

        blocks_state = serialized["blocks"]
        if type(blocks_state) is not dict:
            raise ValueError("authority blocks must use canonical serialized state")
        blocks: dict[str, list[AuthorityBlock]] = {}
        block_numbers: list[int] = []
        for artifact_id, raw_rows in blocks_state.items():
            artifact = _exact_string(artifact_id, "authority block artifact identity")
            rows = _canonical_state_list(raw_rows, "authority block rows")
            parsed_rows: list[AuthorityBlock] = []
            for raw_row in rows:
                row = _canonical_state_record(
                    raw_row,
                    ("block_id", "artifact_id", "blocker_agent_id", "reason"),
                    "authority block",
                )
                block_id = _exact_string(row["block_id"], "authority block identity")
                block_numbers.append(
                    _sequence_number(block_id, "block-", "authority block identity")
                )
                row_artifact = _exact_string(
                    row["artifact_id"], "authority block artifact identity"
                )
                if row_artifact != artifact:
                    raise ValueError("authority block artifact identity does not match its ledger")
                blocker = _exact_string(
                    row["blocker_agent_id"], "authority blocker agent identity"
                )
                try:
                    registry.get(blocker)
                except KeyError as exc:
                    raise ValueError("authority blocker agent identity is unknown") from exc
                reason = _non_empty_string(row["reason"], "authority block reason")
                parsed_rows.append(
                    AuthorityBlock(
                        block_id=block_id,
                        artifact_id=row_artifact,
                        blocker_agent_id=blocker,
                        reason=reason,
                    )
                )
            blocks[artifact] = parsed_rows

        block_counter = _non_negative_int(
            serialized["block_counter"], "authority block counter"
        )
        _validate_sequence_counter(block_numbers, block_counter, "authority block")

        overrides_state = serialized["overrides"]
        if type(overrides_state) is not dict:
            raise ValueError("authority overrides must use canonical serialized state")
        overrides: dict[str, OverrideReceipt] = {}
        override_numbers: list[int] = []
        for outer_override_id, raw_row in overrides_state.items():
            override_key = _exact_string(
                outer_override_id, "authority override identity"
            )
            row = _canonical_state_record(
                raw_row,
                (
                    "override_id",
                    "artifact_id",
                    "actor_agent_id",
                    "reason",
                    "evidence_ids",
                    "overrode_block",
                ),
                "authority override",
            )
            override_id = _exact_string(row["override_id"], "authority override identity")
            if override_id != override_key:
                raise ValueError("authority override identity does not match its ledger key")
            override_numbers.append(
                _sequence_number(override_id, "override-", "authority override identity")
            )
            artifact_id = _exact_string(
                row["artifact_id"], "authority override artifact identity"
            )
            actor_agent_id = _exact_string(
                row["actor_agent_id"], "authority override actor identity"
            )
            if actor_agent_id != "nolane.central":
                raise ValueError("authority override actor must be nolane.central")
            try:
                registry.get(actor_agent_id)
            except KeyError as exc:
                raise ValueError("authority override actor identity is unknown") from exc
            reason = _non_empty_string(row["reason"], "authority override reason")
            evidence_state = _canonical_state_list(
                row["evidence_ids"], "authority override evidence ids"
            )
            if not evidence_state:
                raise ValueError("authority override evidence ids must be explicit")
            evidence_ids = tuple(
                _exact_string(value, "authority override evidence identity")
                for value in evidence_state
            )
            overrode_block = row["overrode_block"]
            if type(overrode_block) is not bool:
                raise ValueError("authority override overrode_block must be an exact boolean")
            if overrode_block and not blocks.get(artifact_id):
                raise ValueError("authority override block claim has no canonical block")
            overrides[override_id] = OverrideReceipt(
                override_id=override_id,
                artifact_id=artifact_id,
                actor_agent_id=actor_agent_id,
                reason=reason,
                evidence_ids=evidence_ids,
                overrode_block=overrode_block,
            )

        override_counter = _non_negative_int(
            serialized["override_counter"], "authority override counter"
        )
        _validate_sequence_counter(override_numbers, override_counter, "authority override")

        graph = cls(registry)
        graph._owners = owners
        graph._blocks = blocks
        graph._overrides = overrides
        graph._block_counter = block_counter
        graph._override_counter = override_counter
        return graph


__all__ = (
    "AuthorityBlock",
    "AuthorityGraph",
    "OverrideReceipt",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
