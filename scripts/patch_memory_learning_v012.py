from __future__ import annotations

from pathlib import Path


SUBSTRATE = Path("nolane/memory/learning_substrate.py")
AUTHORITY = Path("nolane/memory/learning_authority.py")
text = SUBSTRATE.read_text(encoding="utf-8")
authority_text = AUTHORITY.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one substrate patch anchor, got {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


def replace_authority_once(old: str, new: str) -> None:
    global authority_text
    count = authority_text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one authority patch anchor, got {count}: {old[:100]!r}")
    authority_text = authority_text.replace(old, new, 1)


# A small read-only receipt lookup keeps restore validation on the canonical
# LearningEvidenceAuthority instead of manufacturing a second index/ledger.
replace_authority_once(
    '''    def uses_for(self, lease_id: str) -> tuple[LearningEvidenceUseReceipt, ...]:\n        self.lease(lease_id)\n        return tuple(self._uses_by_lease.get(str(lease_id), ()))\n\n''',
    '''    def uses_for(self, lease_id: str) -> tuple[LearningEvidenceUseReceipt, ...]:\n        self.lease(lease_id)\n        return tuple(self._uses_by_lease.get(str(lease_id), ()))\n\n    def use_receipt(self, receipt_id: str) -> LearningEvidenceUseReceipt:\n        try:\n            return self._uses[str(receipt_id)]\n        except KeyError as exc:\n            raise KeyError(f"unknown learning evidence use receipt: {receipt_id}") from exc\n\n''',
)

replace_once(
    "from nolane.core.canonical_digest import canonical_digest\n",
    "from nolane.core.canonical_digest import canonical_digest\n"
    "from nolane.external_core.evidence import EvidenceRecord\n"
    "from nolane.memory.learning_authority import LearningEvidenceAuthority\n",
)

# v0.0.12 rows carry the exact authority-use receipt. None remains accepted only
# for historical v0.0.10/v0.0.11 replay.
replace_once(
    "    content_digest: str\n    event_anchor_id: str | None\n    digest: str\n",
    "    content_digest: str\n    authorization_use_receipt_id: str | None\n    event_anchor_id: str | None\n    digest: str\n",
)
replace_once(
    "        if not str(self.archive_receipt_id).strip() or not str(self.content_digest).strip():\n"
    "            raise ValueError(\"memory forget receipt requires archive and content authority\")\n",
    "        if not str(self.archive_receipt_id).strip() or not str(self.content_digest).strip():\n"
    "            raise ValueError(\"memory forget receipt requires archive and content authority\")\n"
    "        if self.authorization_use_receipt_id is not None and not str(self.authorization_use_receipt_id).strip():\n"
    "            raise ValueError(\"memory forget receipt authorization use receipt must be non-empty\")\n",
)
replace_once(
    "            \"content_digest\": self.content_digest,\n            \"event_anchor_id\": self.event_anchor_id,\n",
    "            \"content_digest\": self.content_digest,\n"
    "            \"authorization_use_receipt_id\": self.authorization_use_receipt_id,\n"
    "            \"event_anchor_id\": self.event_anchor_id,\n",
)
replace_once(
    "            content_digest=str(state[\"content_digest\"]),\n            event_anchor_id=None if state.get(\"event_anchor_id\") is None else str(state[\"event_anchor_id\"]),\n",
    "            content_digest=str(state[\"content_digest\"]),\n"
    "            authorization_use_receipt_id=(\n"
    "                None if state.get(\"authorization_use_receipt_id\") is None\n"
    "                else str(state[\"authorization_use_receipt_id\"])\n"
    "            ),\n"
    "            event_anchor_id=None if state.get(\"event_anchor_id\") is None else str(state[\"event_anchor_id\"]),\n",
)
replace_once(
    "    forget_receipt_id: str | None = None\n",
    "    forget_receipt_id: str | None = None\n    authorization_use_receipt_id: str | None = None\n",
)
replace_once(
    "        if self.forget_receipt_id is not None and not str(self.forget_receipt_id).strip():\n"
    "            raise ValueError(\"memory tombstone forget receipt authority must be non-empty\")\n",
    "        if self.forget_receipt_id is not None and not str(self.forget_receipt_id).strip():\n"
    "            raise ValueError(\"memory tombstone forget receipt authority must be non-empty\")\n"
    "        if self.authorization_use_receipt_id is not None and not str(self.authorization_use_receipt_id).strip():\n"
    "            raise ValueError(\"memory tombstone authorization use receipt must be non-empty\")\n",
)
replace_once(
    "            \"forget_receipt_id\": self.forget_receipt_id,\n",
    "            \"forget_receipt_id\": self.forget_receipt_id,\n"
    "            \"authorization_use_receipt_id\": self.authorization_use_receipt_id,\n",
)
replace_once(
    "            forget_receipt_id=(\n"
    "                None if state.get(\"forget_receipt_id\") is None else str(state[\"forget_receipt_id\"])\n"
    "            ),\n",
    "            forget_receipt_id=(\n"
    "                None if state.get(\"forget_receipt_id\") is None else str(state[\"forget_receipt_id\"])\n"
    "            ),\n"
    "            authorization_use_receipt_id=(\n"
    "                None if state.get(\"authorization_use_receipt_id\") is None\n"
    "                else str(state[\"authorization_use_receipt_id\"])\n"
    "            ),\n",
)

# Bind the substrate and its B children to one authority object.
replace_once(
    "        experiences: ExperienceLedger | None = None,\n    ) -> None:\n",
    "        experiences: ExperienceLedger | None = None,\n"
    "        learning_authority: LearningEvidenceAuthority | None = None,\n"
    "    ) -> None:\n",
)
replace_once(
    "        self.experiences = experiences or ExperienceLedger(registry=registry, events=events)\n",
    "        self.experiences = experiences or ExperienceLedger(registry=registry, events=events)\n"
    "        self.learning_authority = learning_authority or LearningEvidenceAuthority()\n"
    "        for label, component in ((\"skill\", self.skills), (\"experience\", self.experiences)):\n"
    "            bound = getattr(component, \"learning_authority\", None)\n"
    "            if bound is not None and bound is not self.learning_authority:\n"
    "                raise ValueError(f\"learning substrate {label} authority diverges from shared learning authority\")\n"
    "            component.learning_authority = self.learning_authority\n",
)

# Caller-supplied evidence reference strings are data, never admission authority.
# A VERIFIED-looking write is retained as an untrusted hypothesis and quarantined.
replace_once(
    "        kind, epistemic_type = MemoryKind(kind), EpistemicType(epistemic_type)\n"
    "        validated = epistemic_type is EpistemicType.VERIFIED and bool(evidence_ids)\n",
    "        kind, requested_epistemic_type = MemoryKind(kind), EpistemicType(epistemic_type)\n"
    "        epistemic_type = (\n"
    "            EpistemicType.HYPOTHESIS\n"
    "            if requested_epistemic_type is EpistemicType.VERIFIED\n"
    "            else requested_epistemic_type\n"
    "        )\n"
    "        validated = False\n",
)

old_validate = '''    def validate_memory(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        evidence_refs: tuple[str, ...],\n        correction_ref: str,\n    ) -> MemoryEntry:\n        receipt = self.lifecycle.transition(\n            memory_id,\n            actor_agent_id=actor_agent_id,\n            new_status=MemoryStatus.ACTIVE,\n            reason="external_validation_completed",\n            evidence_refs=evidence_refs,\n            correction_ref=correction_ref,\n        )\n        metadata = self.metadata(memory_id)\n        self._metadata[memory_id] = replace(\n            metadata,\n            epistemic_type=EpistemicType.VERIFIED,\n            last_verified_ref=str(correction_ref),\n            source_refs=tuple(sorted(set(metadata.source_refs + receipt.evidence_refs))),\n        )\n        return self.memory.get(memory_id)\n'''
new_validate = '''    def memory_verification_subject_digest(\n        self, memory_id: str, *, actor_agent_id: str | None = None\n    ) -> str:\n        row = self.memory.get(memory_id)\n        metadata = self.metadata(memory_id)\n        actor = None if actor_agent_id is None else str(actor_agent_id).strip()\n        if actor_agent_id is not None and not actor:\n            raise ValueError("memory verification actor must be explicit when supplied")\n        return canonical_digest(\n            {\n                "operation_class": "memory.verify",\n                "current_memory": row.to_state(),\n                "current_metadata": metadata.to_state(),\n                "lifecycle": [receipt.to_state() for receipt in self.lifecycle.receipts_for(row.memory_id)],\n                "actor_agent_id": actor,\n                "proposed_status": MemoryStatus.ACTIVE.value,\n                "proposed_epistemic_type": EpistemicType.VERIFIED.value,\n            }\n        )\n\n    def validate_memory(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        evidence: EvidenceRecord | None = None,\n        authority_lease_id: str | None = None,\n        evidence_refs: tuple[str, ...] | None = None,\n        correction_ref: str | None = None,\n    ) -> MemoryEntry:\n        row = self.memory.get(memory_id)\n        actor = self.registry.get(actor_agent_id)\n        if actor.region != self.lifecycle.REGION:\n            raise PermissionError("verified memory admission requires a Memory/Context actor")\n        if evidence is None:\n            raise PermissionError("verified memory admission requires actual evidence and a preissued learning evidence lease")\n        self.registry.get(evidence.verifier_agent_id)\n        if authority_lease_id is None or not str(authority_lease_id).strip():\n            raise PermissionError("verified memory admission requires a preissued learning evidence lease")\n        subject_digest = self.memory_verification_subject_digest(\n            row.memory_id, actor_agent_id=actor.agent_id\n        )\n        use = self.learning_authority.consume(\n            str(authority_lease_id),\n            subject_kind="memory",\n            subject_id=row.memory_id,\n            operation_class="memory.verify",\n            producer_agent_id=row.owner_agent_id,\n            evidence=evidence,\n            subject_digest=subject_digest,\n            use_ref="memory-verify:" + row.memory_id + ":" + subject_digest[:20],\n        )\n        receipt = self.lifecycle.transition(\n            row.memory_id,\n            actor_agent_id=actor.agent_id,\n            new_status=MemoryStatus.ACTIVE,\n            reason="external_validation_completed",\n            evidence_refs=(evidence.evidence_id,),\n            correction_ref=use.receipt_id,\n        )\n        metadata = self.metadata(row.memory_id)\n        self._metadata[row.memory_id] = replace(\n            metadata,\n            epistemic_type=EpistemicType.VERIFIED,\n            last_verified_ref=evidence.evidence_id,\n            source_refs=tuple(sorted(set(metadata.source_refs + (evidence.evidence_id,)))),\n        )\n        return self.memory.get(row.memory_id)\n'''
replace_once(old_validate, new_validate)

old_forget_head = '''    def forget(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        reason: str,\n        evidence_refs: tuple[str, ...],\n    ) -> MemoryTombstone:\n        row, reason = self.memory.get(memory_id), str(reason).strip()\n        actor_id = str(actor_agent_id).strip()\n        actor = self.registry.get(actor_id)\n        if actor.region != self.lifecycle.REGION:\n            raise PermissionError("forgetting memory requires a Memory/Context identity")\n        evidence = _clean_refs(evidence_refs)\n        if not reason:\n            raise ValueError("forgetting requires an explicit reason")\n        if not evidence:\n            raise ValueError("forgetting requires evidence")\n'''
new_forget_head = '''    def forget_subject_digest(\n        self, memory_id: str, *, actor_agent_id: str, reason: str\n    ) -> str:\n        row = self.memory.get(memory_id)\n        metadata = self.metadata(memory_id)\n        actor_id = str(actor_agent_id).strip()\n        normalized_reason = str(reason).strip()\n        if not actor_id or not normalized_reason:\n            raise ValueError("forget authority requires actor and reason")\n        return canonical_digest(\n            {\n                "operation_class": "memory.forget",\n                "current_memory": row.to_state(),\n                "current_metadata": metadata.to_state(),\n                "lifecycle": [receipt.to_state() for receipt in self.lifecycle.receipts_for(row.memory_id)],\n                "actor_agent_id": actor_id,\n                "reason": normalized_reason,\n            }\n        )\n\n    def forget(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        reason: str,\n        evidence: EvidenceRecord | None = None,\n        authority_lease_id: str | None = None,\n        evidence_refs: tuple[str, ...] | None = None,\n    ) -> MemoryTombstone:\n        row, reason = self.memory.get(memory_id), str(reason).strip()\n        actor_id = str(actor_agent_id).strip()\n        actor = self.registry.get(actor_id)\n        if actor.region != self.lifecycle.REGION:\n            raise PermissionError("forgetting memory requires a Memory/Context identity")\n        if not reason:\n            raise ValueError("forgetting requires an explicit reason")\n\n        content_digest = canonical_digest({"memory_id": row.memory_id, "text": row.text})\n        existing = self._tombstones.get(row.memory_id)\n        if existing is not None:\n            supplied_refs = (\n                (evidence.evidence_id,) if evidence is not None\n                else _clean_refs(tuple(evidence_refs or ()))\n            )\n            if (\n                existing.content_digest != content_digest\n                or existing.reason != reason\n                or existing.actor_agent_id != actor.agent_id\n                or (supplied_refs and existing.evidence_refs != supplied_refs)\n            ):\n                raise ValueError("memory tombstone cannot be rebound")\n            self._validate_tombstone_semantics(existing)\n            return existing\n\n        if evidence is None:\n            raise PermissionError("first-time forgetting requires actual evidence and a preissued learning evidence lease")\n        self.registry.get(evidence.verifier_agent_id)\n        if authority_lease_id is None or not str(authority_lease_id).strip():\n            raise PermissionError("first-time forgetting requires a preissued learning evidence lease")\n        subject_digest = self.forget_subject_digest(\n            row.memory_id, actor_agent_id=actor.agent_id, reason=reason\n        )\n        authorization = self.learning_authority.consume(\n            str(authority_lease_id),\n            subject_kind="memory",\n            subject_id=row.memory_id,\n            operation_class="memory.forget",\n            producer_agent_id=actor.agent_id,\n            evidence=evidence,\n            subject_digest=subject_digest,\n            use_ref="memory-forget-authority:" + row.memory_id + ":" + subject_digest[:20],\n        )\n        evidence = _clean_refs((evidence.evidence_id,))\n'''
replace_once(old_forget_head, new_forget_head)

# The old implementation repeats content/tombstone checks after the head.
replace_once(
    '''\n        content_digest = canonical_digest({"memory_id": row.memory_id, "text": row.text})\n        existing = self._tombstones.get(row.memory_id)\n        if existing is not None:\n            if (\n                existing.content_digest != content_digest\n                or existing.reason != reason\n                or existing.evidence_refs != evidence\n                or existing.actor_agent_id != actor.agent_id\n            ):\n                raise ValueError("memory tombstone cannot be rebound")\n            self._validate_tombstone_semantics(existing)\n            return existing\n\n''',
    "\n",
)
replace_once(
    '''            "content_digest": content_digest,\n            "event_anchor_id": event_anchor_id,\n''',
    '''            "content_digest": content_digest,\n            "authorization_use_receipt_id": authorization.receipt_id,\n            "event_anchor_id": event_anchor_id,\n''',
)
replace_once(
    '''            content_digest=content_digest,\n            event_anchor_id=event_anchor_id,\n            digest=canonical_digest(payload),\n''',
    '''            content_digest=content_digest,\n            authorization_use_receipt_id=authorization.receipt_id,\n            event_anchor_id=event_anchor_id,\n            digest=canonical_digest(payload),\n''',
)
replace_once(
    '''            forget_receipt_id=receipt_id,\n        )\n''',
    '''            forget_receipt_id=receipt_id,\n            authorization_use_receipt_id=authorization.receipt_id,\n        )\n''',
)

# Canonical restore accepts an injected existing authority ledger, without
# re-consuming capabilities while replaying historical rows.
replace_once(
    '    def from_state(cls, *, registry, events, state: Mapping[str, Any]) -> "LearningSubstrate":\n',
    '    def from_state(\n'
    '        cls, *, registry, events, state: Mapping[str, Any],\n'
    '        learning_authority: LearningEvidenceAuthority | None = None,\n'
    '    ) -> "LearningSubstrate":\n',
)
replace_once(
    '''            experiences=ExperienceLedger.from_state(\n                registry=registry,\n                events=events,\n                state=state.get("experiences", {}),\n            ),\n        )\n''',
    '''            experiences=ExperienceLedger.from_state(\n                registry=registry,\n                events=events,\n                state=state.get("experiences", {}),\n                learning_authority=learning_authority,\n            ),\n            learning_authority=learning_authority,\n        )\n''',
)
replace_once(
    '            skills=SkillEvolutionEngine.from_state(state.get("skills", {})),\n',
    '            skills=SkillEvolutionEngine.from_state(\n'
    '                state.get("skills", {}), learning_authority=learning_authority\n'
    '            ),\n',
)

# New admission activation receipts must resolve to an exact memory.verify use.
old_metadata_tail = '''        lifecycle_rows = self.lifecycle.receipts_for(row.memory_id)\n        activation = lifecycle_rows[-1] if lifecycle_rows else None\n        if (\n            activation is None\n            or activation.new_status is not MemoryStatus.ACTIVE\n            or not activation.evidence_refs\n            or not str(activation.correction_ref or "").strip()\n        ):\n            raise ValueError("active learning memory requires verification proof")\n'''
new_metadata_tail = old_metadata_tail + '''        if str(activation.correction_ref).startswith("learning-evidence-use-"):\n            try:\n                use = self.learning_authority.use_receipt(str(activation.correction_ref))\n            except KeyError as exc:\n                raise ValueError("active learning memory verification authority receipt is missing") from exc\n            if (\n                use.subject_kind != "memory"\n                or use.subject_id != row.memory_id\n                or use.operation_class != "memory.verify"\n                or use.producer_agent_id != row.owner_agent_id\n                or use.evidence_id not in activation.evidence_refs\n                or use.evidence_id != metadata.last_verified_ref\n            ):\n                raise ValueError("active learning memory verification authority does not match exact memory")\n'''
replace_once(old_metadata_tail, new_metadata_tail)

old_tombstone_tail = '''        if (\n            forget_receipt.memory_id != tombstone.memory_id\n            or forget_receipt.actor_agent_id != tombstone.actor_agent_id\n            or forget_receipt.archive_receipt_id != tombstone.archive_receipt_id\n            or forget_receipt.reason != tombstone.reason\n            or forget_receipt.evidence_refs != tombstone.evidence_refs\n            or forget_receipt.content_digest != tombstone.content_digest\n        ):\n            raise ValueError("memory tombstone disagrees with forget authorization receipt")\n        self._validate_forget_receipt_semantics(forget_receipt)\n'''
new_tombstone_tail = '''        if (\n            forget_receipt.memory_id != tombstone.memory_id\n            or forget_receipt.actor_agent_id != tombstone.actor_agent_id\n            or forget_receipt.archive_receipt_id != tombstone.archive_receipt_id\n            or forget_receipt.reason != tombstone.reason\n            or forget_receipt.evidence_refs != tombstone.evidence_refs\n            or forget_receipt.content_digest != tombstone.content_digest\n            or forget_receipt.authorization_use_receipt_id != tombstone.authorization_use_receipt_id\n        ):\n            raise ValueError("memory tombstone disagrees with forget authorization receipt")\n        if forget_receipt.authorization_use_receipt_id is not None:\n            try:\n                use = self.learning_authority.use_receipt(forget_receipt.authorization_use_receipt_id)\n            except KeyError as exc:\n                raise ValueError("memory forget authorization use receipt is missing") from exc\n            if (\n                use.subject_kind != "memory"\n                or use.subject_id != forget_receipt.memory_id\n                or use.operation_class != "memory.forget"\n                or use.producer_agent_id != forget_receipt.actor_agent_id\n                or use.evidence_id not in forget_receipt.evidence_refs\n            ):\n                raise ValueError("memory forget authorization receipt does not match exact forgetting authority")\n        self._validate_forget_receipt_semantics(forget_receipt)\n'''
replace_once(old_tombstone_tail, new_tombstone_tail)

SUBSTRATE.write_text(text, encoding="utf-8")
AUTHORITY.write_text(authority_text, encoding="utf-8")
print("patched", SUBSTRATE)
print("patched", AUTHORITY)
