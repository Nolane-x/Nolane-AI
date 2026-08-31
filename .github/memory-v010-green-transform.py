from pathlib import Path

PATH = Path("nolane/memory/learning_substrate.py")
text = PATH.read_text()


def replace_between(source: str, start: str, end: str, replacement: str, label: str) -> str:
    if source.count(start) < 1 or source.count(end) < 1:
        raise SystemExit(f"unexpected source markers for {label}")
    begin = source.index(start)
    finish = source.index(end, begin)
    old = source[begin:finish]
    if replacement.rstrip() in source:
        print(f"already applied: {label}")
        return source
    print(f"applied: {label}")
    return source[:begin] + replacement + source[finish:]


TOMBSTONE = '''@dataclass(frozen=True, slots=True)
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
            archive_receipt_id=(
                None if state.get("archive_receipt_id") is None else str(state["archive_receipt_id"])
            ),
        )


'''
text = replace_between(
    text,
    "@dataclass(frozen=True, slots=True)\nclass MemoryTombstone:",
    "@dataclass(frozen=True, slots=True)\nclass RetrievedLearningMemory:",
    TOMBSTONE,
    "MemoryTombstone authority schema",
)

FORGET = '''    def forget(
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
text = replace_between(
    text,
    "    def forget(\n",
    "    def tombstone(\n",
    FORGET,
    "forget authorization binding",
)

VALIDATE = '''    def _validate_tombstone_semantics(self, tombstone: MemoryTombstone) -> None:
        row = self.memory.get(tombstone.memory_id)
        if row.status is not MemoryStatus.ARCHIVED:
            raise ValueError("memory tombstone requires archived memory state")
        if tombstone.actor_agent_id is None or tombstone.archive_receipt_id is None:
            raise ValueError("memory tombstone requires forgetting authorization proof")
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
text = replace_between(
    text,
    "    def _validate_tombstone_semantics(self, tombstone: MemoryTombstone) -> None:\n",
    "    def to_state(self) -> dict[str, Any]:\n",
    VALIDATE,
    "tombstone restore authorization",
)

PATH.write_text(text)
