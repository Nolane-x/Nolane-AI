from pathlib import Path

path = Path("nolane/memory/learning_substrate.py")
text = path.read_text()

old_schema = '''@dataclass(frozen=True, slots=True)
class MemoryTombstone:
    memory_id: str
    content_digest: str
    reason: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not str(self.memory_id).strip():
            raise ValueError("memory tombstone requires a memory id")
        if not str(self.content_digest).strip():
            raise ValueError("memory tombstone requires a content digest")
        if not str(self.reason).strip():
            raise ValueError("memory tombstone requires a reason")
        if not self.evidence_refs or any(not str(value).strip() for value in self.evidence_refs):
            raise ValueError("memory tombstone requires non-empty evidence")

    def to_state(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content_digest": self.content_digest,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryTombstone":
        return cls(
            str(state["memory_id"]),
            str(state["content_digest"]),
            str(state["reason"]),
            tuple(str(x) for x in state.get("evidence_refs", ())),
        )
'''
new_schema = '''@dataclass(frozen=True, slots=True)
class MemoryTombstone:
    memory_id: str
    content_digest: str
    reason: str
    evidence_refs: tuple[str, ...]
    actor_agent_id: str | None = None
    archive_receipt_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.memory_id).strip():
            raise ValueError("memory tombstone requires a memory id")
        if not str(self.content_digest).strip():
            raise ValueError("memory tombstone requires a content digest")
        if not str(self.reason).strip():
            raise ValueError("memory tombstone requires a reason")
        if not self.evidence_refs or any(not str(value).strip() for value in self.evidence_refs):
            raise ValueError("memory tombstone requires non-empty evidence")
        if self.actor_agent_id is not None and not str(self.actor_agent_id).strip():
            raise ValueError("memory tombstone actor authority must be non-empty")
        if self.archive_receipt_id is not None and not str(self.archive_receipt_id).strip():
            raise ValueError("memory tombstone archive receipt authority must be non-empty")

    def to_state(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content_digest": self.content_digest,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "actor_agent_id": self.actor_agent_id,
            "archive_receipt_id": self.archive_receipt_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryTombstone":
        return cls(
            memory_id=str(state["memory_id"]),
            content_digest=str(state["content_digest"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            actor_agent_id=None if state.get("actor_agent_id") is None else str(state["actor_agent_id"]),
            archive_receipt_id=None if state.get("archive_receipt_id") is None else str(state["archive_receipt_id"]),
        )
'''

old_forget = '''    def forget(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> MemoryTombstone:
        row, reason = self.memory.get(memory_id), str(reason).strip()
        actor = self.registry.get(str(actor_agent_id).strip())
        if actor.region != self.lifecycle.REGION:
            raise PermissionError("forgetting memory requires a Memory/Context identity")
        evidence = _clean_refs(evidence_refs)
        if not reason:
            raise ValueError("forgetting requires an explicit reason")
        if not evidence:
            raise ValueError("forgetting requires evidence")
        candidate = MemoryTombstone(
            row.memory_id,
            canonical_digest({"memory_id": row.memory_id, "text": row.text}),
            reason,
            evidence,
        )
        existing = self._tombstones.get(row.memory_id)
        if existing is not None:
            if existing != candidate:
                raise ValueError("memory tombstone cannot be rebound")
            return existing
        if row.status is not MemoryStatus.ARCHIVED:
            self.lifecycle.transition(
                row.memory_id,
                actor_agent_id=actor_agent_id,
                new_status=MemoryStatus.ARCHIVED,
                reason=reason,
                evidence_refs=evidence,
            )
        self._tombstones[row.memory_id] = candidate
        return candidate
'''
new_forget = '''    def forget(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> MemoryTombstone:
        row, reason = self.memory.get(memory_id), str(reason).strip()
        actor_id = str(actor_agent_id).strip()
        actor = self.registry.get(actor_id)
        if actor.region != self.lifecycle.REGION:
            raise PermissionError("forgetting memory requires a Memory/Context identity")
        evidence = _clean_refs(evidence_refs)
        if not reason:
            raise ValueError("forgetting requires an explicit reason")
        if not evidence:
            raise ValueError("forgetting requires evidence")

        content_digest = canonical_digest({"memory_id": row.memory_id, "text": row.text})
        existing = self._tombstones.get(row.memory_id)
        if existing is not None:
            candidate = MemoryTombstone(
                memory_id=row.memory_id,
                content_digest=content_digest,
                reason=reason,
                evidence_refs=evidence,
                actor_agent_id=actor.agent_id,
                archive_receipt_id=existing.archive_receipt_id,
            )
            if existing != candidate:
                raise ValueError("memory tombstone cannot be rebound")
            self._validate_tombstone_semantics(existing)
            return existing

        if row.status is not MemoryStatus.ARCHIVED:
            archive_receipt = self.lifecycle.transition(
                row.memory_id,
                actor_agent_id=actor.agent_id,
                new_status=MemoryStatus.ARCHIVED,
                reason=reason,
                evidence_refs=evidence,
            )
        else:
            archive_receipt = next(
                (
                    receipt
                    for receipt in reversed(self.lifecycle.receipts_for(row.memory_id))
                    if receipt.new_status is MemoryStatus.ARCHIVED
                ),
                None,
            )
            if archive_receipt is None:
                raise ValueError("forgetting archived memory requires archived lifecycle authority")

        candidate = MemoryTombstone(
            memory_id=row.memory_id,
            content_digest=content_digest,
            reason=reason,
            evidence_refs=evidence,
            actor_agent_id=actor.agent_id,
            archive_receipt_id=archive_receipt.receipt_id,
        )
        self._validate_tombstone_semantics(candidate)
        self._tombstones[row.memory_id] = candidate
        return candidate
'''

old_validator = '''    def _validate_tombstone_semantics(self, tombstone: MemoryTombstone) -> None:
        row = self.memory.get(tombstone.memory_id)
        if row.status is not MemoryStatus.ARCHIVED:
            raise ValueError("memory tombstone requires archived memory state")
        archived = any(
            receipt.new_status is MemoryStatus.ARCHIVED
            for receipt in self.lifecycle.receipts_for(tombstone.memory_id)
        )
        if not archived:
            raise ValueError("memory tombstone requires archived lifecycle authority")
'''
new_validator = '''    def _validate_tombstone_semantics(self, tombstone: MemoryTombstone) -> None:
        row = self.memory.get(tombstone.memory_id)
        if row.status is not MemoryStatus.ARCHIVED:
            raise ValueError("memory tombstone requires archived memory state")
        if tombstone.actor_agent_id is None or tombstone.archive_receipt_id is None:
            raise ValueError("memory tombstone requires forgetting authorization")
        actor = self.registry.get(tombstone.actor_agent_id)
        if actor.region != self.lifecycle.REGION:
            raise PermissionError("memory tombstone actor requires Memory/Context authority")
        archive_receipt = next(
            (
                receipt
                for receipt in self.lifecycle.receipts_for(tombstone.memory_id)
                if receipt.receipt_id == tombstone.archive_receipt_id
            ),
            None,
        )
        if archive_receipt is None or archive_receipt.new_status is not MemoryStatus.ARCHIVED:
            raise ValueError("memory tombstone requires archived lifecycle authority")
'''

for label, old, new in (
    ("MemoryTombstone schema", old_schema, new_schema),
    ("forget authorization binding", old_forget, new_forget),
    ("tombstone restore authorization", old_validator, new_validator),
):
    old_count = text.count(old)
    new_count = text.count(new)
    if old_count == 1 and new_count == 0:
        text = text.replace(old, new, 1)
        print(f"applied: {label}")
    elif old_count == 0 and new_count == 1:
        print(f"already applied: {label}")
    else:
        raise SystemExit(f"unexpected source markers for {label}: old={old_count} new={new_count}")

path.write_text(text)
