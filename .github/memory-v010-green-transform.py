from pathlib import Path
import re

PATH = Path("nolane/memory/learning_substrate.py")
text = PATH.read_text()


def replace_between(source: str, start: str, end: str, replacement: str, label: str) -> str:
    if replacement.rstrip() in source:
        print(f"already applied: {label}")
        return source
    if source.count(start) < 1 or source.count(end) < 1:
        raise SystemExit(f"unexpected source markers for {label}")
    begin = source.index(start)
    finish = source.index(end, begin)
    print(f"applied: {label}")
    return source[:begin] + replacement + source[finish:]


def replace_method_block(source: str, start_name: str, end_name: str, replacement: str, label: str) -> str:
    if replacement.rstrip() in source:
        print(f"already applied: {label}")
        return source
    pattern = re.compile(
        rf"(?ms)^    def {re.escape(start_name)}\(.*?(?=^    def {re.escape(end_name)}\()"
    )
    updated, count = pattern.subn(lambda _match: replacement, source, count=1)
    if count != 1:
        raise SystemExit(f"unexpected source method boundaries for {label}: {count}")
    print(f"applied: {label}")
    return updated


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        print(f"already applied: {label}")
        return source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"unexpected exact source count for {label}: {count}")
    print(f"applied: {label}")
    return source.replace(old, new, 1)


AUTHORITY_SCHEMA = '''@dataclass(frozen=True, slots=True)
class MemoryForgetReceipt:
    sequence: int
    receipt_id: str
    memory_id: str
    actor_agent_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    archive_receipt_id: str
    content_digest: str
    event_anchor_id: str | None
    digest: str

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise ValueError("memory forget receipt sequence must be positive")
        if self.receipt_id != f"memory-forget-{self.sequence:08d}":
            raise ValueError("memory forget receipt sequence/id mismatch")
        if not str(self.memory_id).strip() or not str(self.actor_agent_id).strip():
            raise ValueError("memory forget receipt requires memory and actor authority")
        if not str(self.reason).strip():
            raise ValueError("memory forget receipt requires an explicit reason")
        if not self.evidence_refs or any(not str(value).strip() for value in self.evidence_refs):
            raise ValueError("memory forget receipt requires evidence")
        if not str(self.archive_receipt_id).strip() or not str(self.content_digest).strip():
            raise ValueError("memory forget receipt requires archive and content authority")

    def payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "receipt_id": self.receipt_id,
            "memory_id": self.memory_id,
            "actor_agent_id": self.actor_agent_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "archive_receipt_id": self.archive_receipt_id,
            "content_digest": self.content_digest,
            "event_anchor_id": self.event_anchor_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryForgetReceipt":
        row = cls(
            sequence=int(state["sequence"]),
            receipt_id=str(state["receipt_id"]),
            memory_id=str(state["memory_id"]),
            actor_agent_id=str(state["actor_agent_id"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(value) for value in state.get("evidence_refs", ())),
            archive_receipt_id=str(state["archive_receipt_id"]),
            content_digest=str(state["content_digest"]),
            event_anchor_id=None if state.get("event_anchor_id") is None else str(state["event_anchor_id"]),
            digest=str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("memory forget receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class MemoryTombstone:
    memory_id: str
    content_digest: str
    reason: str
    evidence_refs: tuple[str, ...]
    actor_agent_id: str | None = None
    archive_receipt_id: str | None = None
    forget_receipt_id: str | None = None

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
        if self.forget_receipt_id is not None and not str(self.forget_receipt_id).strip():
            raise ValueError("memory tombstone forget receipt authority must be non-empty")

    def to_state(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content_digest": self.content_digest,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "actor_agent_id": self.actor_agent_id,
            "archive_receipt_id": self.archive_receipt_id,
            "forget_receipt_id": self.forget_receipt_id,
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
            forget_receipt_id=(
                None if state.get("forget_receipt_id") is None else str(state["forget_receipt_id"])
            ),
        )


'''
text = replace_between(
    text,
    "@dataclass(frozen=True, slots=True)\nclass MemoryTombstone:",
    "@dataclass(frozen=True, slots=True)\nclass RetrievedLearningMemory:",
    AUTHORITY_SCHEMA,
    "forget receipt and tombstone authority schema",
)

text = replace_once(
    text,
    '        self._tombstones: dict[str, MemoryTombstone] = {}\n        self._skill_validations: dict[str, SkillValidation] = {}\n',
    '        self._tombstones: dict[str, MemoryTombstone] = {}\n        self._forget_receipts: dict[str, MemoryForgetReceipt] = {}\n        self._forget_counter = 0\n        self._skill_validations: dict[str, SkillValidation] = {}\n',
    "forget ledger initialization",
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
            if (
                existing.content_digest != content_digest
                or existing.reason != reason
                or existing.evidence_refs != evidence
                or existing.actor_agent_id != actor.agent_id
            ):
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

        self._forget_counter += 1
        sequence = self._forget_counter
        receipt_id = f"memory-forget-{sequence:08d}"
        event_anchor_id = self.events.latest_event_id()
        payload = {
            "sequence": sequence,
            "receipt_id": receipt_id,
            "memory_id": row.memory_id,
            "actor_agent_id": actor.agent_id,
            "reason": reason,
            "evidence_refs": list(evidence),
            "archive_receipt_id": archive_receipt.receipt_id,
            "content_digest": content_digest,
            "event_anchor_id": event_anchor_id,
        }
        forget_receipt = MemoryForgetReceipt(
            sequence=sequence,
            receipt_id=receipt_id,
            memory_id=row.memory_id,
            actor_agent_id=actor.agent_id,
            reason=reason,
            evidence_refs=evidence,
            archive_receipt_id=archive_receipt.receipt_id,
            content_digest=content_digest,
            event_anchor_id=event_anchor_id,
            digest=canonical_digest(payload),
        )
        self._validate_forget_receipt_semantics(forget_receipt)
        self._forget_receipts[receipt_id] = forget_receipt

        candidate = MemoryTombstone(
            memory_id=row.memory_id,
            content_digest=content_digest,
            reason=reason,
            evidence_refs=evidence,
            actor_agent_id=actor.agent_id,
            archive_receipt_id=archive_receipt.receipt_id,
            forget_receipt_id=receipt_id,
        )
        self._tombstones[row.memory_id] = candidate
        self._validate_tombstone_semantics(candidate)
        self._validate_forget_ledger_semantics()
        return candidate

'''
text = replace_method_block(
    text,
    "forget",
    "tombstone",
    FORGET,
    "forget authorization receipt issuance",
)

SNAPSHOT = '''    def _retrieval_state_snapshot(self) -> dict[str, Any]:
        return {
            "memory": self.memory.to_state(),
            "lifecycle": self.lifecycle.to_state(),
            "metadata": [self._metadata[key].to_state() for key in sorted(self._metadata)],
            "tombstones": [self._tombstones[key].to_state() for key in sorted(self._tombstones)],
            "forget_receipts": [
                receipt.to_state()
                for receipt in sorted(self._forget_receipts.values(), key=lambda row: row.sequence)
            ],
            "forget_counter": self._forget_counter,
            "relations": self.relations.to_state(),
            "anchor_health": [receipt.to_state() for receipt in self._ordered_anchor_health()],
        }

'''
text = replace_method_block(
    text,
    "_retrieval_state_snapshot",
    "_retrieval_state_digest",
    SNAPSHOT,
    "retrieval snapshot forget authority",
)

replay_old = '''        replay_tombstones = tuple(
            MemoryTombstone.from_state(raw) for raw in snapshot.get("tombstones", ())
        )
'''
replay_new = '''        replay_forget_receipts = tuple(
            MemoryForgetReceipt.from_state(raw) for raw in snapshot.get("forget_receipts", ())
        )
        replay._forget_receipts = self._index_unique(
            replay_forget_receipts, key=lambda row: row.receipt_id, label="retrieval replay forget receipt row"
        )
        replay._forget_counter = int(snapshot.get("forget_counter", len(replay_forget_receipts)))
        replay_tombstones = tuple(
            MemoryTombstone.from_state(raw) for raw in snapshot.get("tombstones", ())
        )
'''
text = replace_once(text, replay_old, replay_new, "retrieval replay forget receipt loading")

VALIDATORS = '''    def _validate_forget_receipt_semantics(self, receipt: MemoryForgetReceipt) -> None:
        row = self.memory.get(receipt.memory_id)
        if row.status is not MemoryStatus.ARCHIVED:
            raise ValueError("memory forget receipt requires archived memory state")
        actor = self.registry.get(receipt.actor_agent_id)
        if actor.region != self.lifecycle.REGION:
            raise PermissionError("memory forget receipt actor requires Memory/Context authority")
        if receipt.evidence_refs != _clean_refs(receipt.evidence_refs):
            raise ValueError("memory forget receipt evidence refs are not canonical")
        expected_digest = canonical_digest({"memory_id": row.memory_id, "text": row.text})
        if receipt.content_digest != expected_digest:
            raise ValueError("memory forget receipt content digest mismatch")
        archive_receipt = next(
            (
                candidate
                for candidate in self.lifecycle.receipts_for(receipt.memory_id)
                if candidate.receipt_id == receipt.archive_receipt_id
            ),
            None,
        )
        if archive_receipt is None or archive_receipt.new_status is not MemoryStatus.ARCHIVED:
            raise ValueError("memory forget receipt requires archived lifecycle authority")
        if receipt.event_anchor_id is not None:
            self.events.get(receipt.event_anchor_id)

    def _validate_forget_ledger_semantics(self) -> None:
        ordered = tuple(sorted(self._forget_receipts.values(), key=lambda row: row.sequence))
        if self._forget_counter != len(ordered):
            raise ValueError("memory forget receipt sequence counter mismatch")
        if [row.sequence for row in ordered] != list(range(1, len(ordered) + 1)):
            raise ValueError("memory forget receipt sequence invariant violated")
        if len({row.memory_id for row in ordered}) != len(ordered):
            raise ValueError("memory forget authority cannot be rebound to the same memory")
        for receipt in ordered:
            if receipt.receipt_id != f"memory-forget-{receipt.sequence:08d}":
                raise ValueError("memory forget receipt id sequence mismatch")
            self._validate_forget_receipt_semantics(receipt)
        referenced = {row.forget_receipt_id for row in self._tombstones.values()}
        if None in referenced:
            raise ValueError("memory tombstone requires forget authorization receipt")
        if referenced != set(self._forget_receipts):
            raise ValueError("memory forget authorization ledger contains orphan or missing receipts")

    def _validate_tombstone_semantics(self, tombstone: MemoryTombstone) -> None:
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
        if tombstone.forget_receipt_id is None:
            raise ValueError("memory tombstone requires forget authorization receipt")
        forget_receipt = self._forget_receipts.get(tombstone.forget_receipt_id)
        if forget_receipt is None:
            raise ValueError("memory tombstone forget authorization receipt is missing")
        if (
            forget_receipt.memory_id != tombstone.memory_id
            or forget_receipt.actor_agent_id != tombstone.actor_agent_id
            or forget_receipt.archive_receipt_id != tombstone.archive_receipt_id
            or forget_receipt.reason != tombstone.reason
            or forget_receipt.evidence_refs != tombstone.evidence_refs
            or forget_receipt.content_digest != tombstone.content_digest
        ):
            raise ValueError("memory tombstone disagrees with forget authorization receipt")
        self._validate_forget_receipt_semantics(forget_receipt)

'''
text = replace_method_block(
    text,
    "_validate_tombstone_semantics",
    "to_state",
    VALIDATORS,
    "forget and tombstone restore authorization",
)

text = replace_once(
    text,
    '            "tombstones": [self._tombstones[key].to_state() for key in sorted(self._tombstones)],\n            "skill_validations": [\n',
    '            "tombstones": [self._tombstones[key].to_state() for key in sorted(self._tombstones)],\n            "forget_receipts": [\n                receipt.to_state()\n                for receipt in sorted(self._forget_receipts.values(), key=lambda row: row.sequence)\n            ],\n            "forget_counter": self._forget_counter,\n            "skill_validations": [\n',
    "persist forget authorization ledger",
)

from_old = '''        tombstones = tuple(MemoryTombstone.from_state(raw) for raw in state.get("tombstones", ()))
        result._tombstones = cls._index_unique(
            tombstones, key=lambda row: row.memory_id, label="memory tombstone row"
        )
'''
from_new = '''        forget_receipts = tuple(
            MemoryForgetReceipt.from_state(raw) for raw in state.get("forget_receipts", ())
        )
        result._forget_receipts = cls._index_unique(
            forget_receipts, key=lambda row: row.receipt_id, label="memory forget receipt row"
        )
        result._forget_counter = int(state.get("forget_counter", len(forget_receipts)))
        tombstones = tuple(MemoryTombstone.from_state(raw) for raw in state.get("tombstones", ()))
        result._tombstones = cls._index_unique(
            tombstones, key=lambda row: row.memory_id, label="memory tombstone row"
        )
'''
text = replace_once(text, from_old, from_new, "restore forget authorization ledger")

main_loop_old = '''        for skill_id, validation in result._skill_validations.items():
'''
main_loop_new = '''        result._validate_forget_ledger_semantics()
        for skill_id, validation in result._skill_validations.items():
'''
text = replace_once(text, main_loop_old, main_loop_new, "validate restored forget authorization ledger")

replay_loop_old = '''        for row in replay_health:
            replay._anchor_health.setdefault(row.memory_id, []).append(row)
            replay._validate_anchor_health_receipt_semantics(row)

        replay._retrieval_policies = dict(self._retrieval_policies)
'''
replay_loop_new = '''        for row in replay_health:
            replay._anchor_health.setdefault(row.memory_id, []).append(row)
            replay._validate_anchor_health_receipt_semantics(row)
        replay._validate_forget_ledger_semantics()

        replay._retrieval_policies = dict(self._retrieval_policies)
'''
text = replace_once(text, replay_loop_old, replay_loop_new, "validate retrieval replay forget authorization ledger")

PATH.write_text(text)
