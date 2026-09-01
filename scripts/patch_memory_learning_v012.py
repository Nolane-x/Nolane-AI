from __future__ import annotations

from pathlib import Path


PATH = Path("nolane/memory/learning_substrate.py")
text = PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one patch anchor, got {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)


replace_once(
    "from nolane.core.canonical_digest import canonical_digest\n",
    "from nolane.core.canonical_digest import canonical_digest\n"
    "from nolane.external_core.evidence import EvidenceRecord\n"
    "from nolane.memory.learning_authority import LearningEvidenceAuthority\n",
)

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

replace_once(
    "        experiences: ExperienceLedger | None = None,\n    ) -> None:\n",
    "        experiences: ExperienceLedger | None = None,\n"
    "        learning_authority: LearningEvidenceAuthority | None = None,\n"
    "    ) -> None:\n",
)
replace_once(
    "        self.experiences = experiences or ExperienceLedger(registry=registry, events=events)\n",
    "        self.experiences = experiences or ExperienceLedger(registry=registry, events=events)\n"
    "        self.learning_authority = learning_authority or LearningEvidenceAuthority()\n",
)

replace_once(
    "        kind, epistemic_type = MemoryKind(kind), EpistemicType(epistemic_type)\n"
    "        validated = epistemic_type is EpistemicType.VERIFIED and bool(evidence_ids)\n",
    "        kind, requested_epistemic_type = MemoryKind(kind), EpistemicType(epistemic_type)\n"
    "        epistemic_type = (\n"
    "            EpistemicType.OBSERVATION\n"
    "            if requested_epistemic_type is EpistemicType.VERIFIED\n"
    "            else requested_epistemic_type\n"
    "        )\n"
    "        validated = False\n",
)

old_validate = '''    def validate_memory(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        evidence_refs: tuple[str, ...],\n        correction_ref: str,\n    ) -> MemoryEntry:\n        receipt = self.lifecycle.transition(\n            memory_id,\n            actor_agent_id=actor_agent_id,\n            new_status=MemoryStatus.ACTIVE,\n            reason="external_validation_completed",\n            evidence_refs=evidence_refs,\n            correction_ref=correction_ref,\n        )\n        metadata = self.metadata(memory_id)\n        self._metadata[memory_id] = replace(\n            metadata,\n            epistemic_type=EpistemicType.VERIFIED,\n            last_verified_ref=str(correction_ref),\n            source_refs=tuple(sorted(set(metadata.source_refs + receipt.evidence_refs))),\n        )\n        return self.memory.get(memory_id)\n'''
new_validate = '''    def memory_verification_subject_digest(self, memory_id: str) -> str:\n        row = self.memory.get(memory_id)\n        metadata = self.metadata(memory_id)\n        return canonical_digest(\n            {\n                "operation_class": "memory.verify",\n                "current_memory": row.to_state(),\n                "current_metadata": metadata.to_state(),\n                "lifecycle": [receipt.to_state() for receipt in self.lifecycle.receipts_for(row.memory_id)],\n                "proposed_status": MemoryStatus.ACTIVE.value,\n                "proposed_epistemic_type": EpistemicType.VERIFIED.value,\n            }\n        )\n\n    def validate_memory(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        evidence: EvidenceRecord | None = None,\n        authority_lease_id: str | None = None,\n        evidence_refs: tuple[str, ...] | None = None,\n        correction_ref: str | None = None,\n    ) -> MemoryEntry:\n        row = self.memory.get(memory_id)\n        if evidence is None:\n            raise PermissionError("verified memory admission requires actual evidence and a preissued learning evidence lease")\n        self.registry.get(evidence.verifier_agent_id)\n        if authority_lease_id is None or not str(authority_lease_id).strip():\n            raise PermissionError("verified memory admission requires a preissued learning evidence lease")\n        subject_digest = self.memory_verification_subject_digest(row.memory_id)\n        use = self.learning_authority.consume(\n            str(authority_lease_id),\n            subject_kind="memory",\n            subject_id=row.memory_id,\n            operation_class="memory.verify",\n            producer_agent_id=row.owner_agent_id,\n            evidence=evidence,\n            subject_digest=subject_digest,\n            use_ref="memory-verify:" + row.memory_id + ":" + subject_digest[:20],\n        )\n        receipt = self.lifecycle.transition(\n            row.memory_id,\n            actor_agent_id=actor_agent_id,\n            new_status=MemoryStatus.ACTIVE,\n            reason="external_validation_completed",\n            evidence_refs=(evidence.evidence_id,),\n            correction_ref=use.receipt_id,\n        )\n        metadata = self.metadata(row.memory_id)\n        self._metadata[row.memory_id] = replace(\n            metadata,\n            epistemic_type=EpistemicType.VERIFIED,\n            last_verified_ref=evidence.evidence_id,\n            source_refs=tuple(sorted(set(metadata.source_refs + receipt.evidence_refs))),\n        )\n        return self.memory.get(row.memory_id)\n'''
replace_once(old_validate, new_validate)

forget_anchor = '''    def forget(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        reason: str,\n        evidence_refs: tuple[str, ...],\n    ) -> MemoryTombstone:\n        row, reason = self.memory.get(memory_id), str(reason).strip()\n        actor_id = str(actor_agent_id).strip()\n        actor = self.registry.get(actor_id)\n        if actor.region != self.lifecycle.REGION:\n            raise PermissionError("forgetting memory requires a Memory/Context identity")\n        evidence = _clean_refs(evidence_refs)\n        if not reason:\n            raise ValueError("forgetting requires an explicit reason")\n        if not evidence:\n            raise ValueError("forgetting requires evidence")\n'''
forget_replacement = '''    def forget_subject_digest(\n        self, memory_id: str, *, actor_agent_id: str, reason: str\n    ) -> str:\n        row = self.memory.get(memory_id)\n        metadata = self.metadata(memory_id)\n        actor_id = str(actor_agent_id).strip()\n        normalized_reason = str(reason).strip()\n        if not actor_id or not normalized_reason:\n            raise ValueError("forget authority requires actor and reason")\n        return canonical_digest(\n            {\n                "operation_class": "memory.forget",\n                "current_memory": row.to_state(),\n                "current_metadata": metadata.to_state(),\n                "lifecycle": [receipt.to_state() for receipt in self.lifecycle.receipts_for(row.memory_id)],\n                "actor_agent_id": actor_id,\n                "reason": normalized_reason,\n            }\n        )\n\n    def forget(\n        self,\n        memory_id: str,\n        *,\n        actor_agent_id: str,\n        reason: str,\n        evidence: EvidenceRecord | None = None,\n        authority_lease_id: str | None = None,\n        evidence_refs: tuple[str, ...] | None = None,\n    ) -> MemoryTombstone:\n        row, reason = self.memory.get(memory_id), str(reason).strip()\n        actor_id = str(actor_agent_id).strip()\n        actor = self.registry.get(actor_id)\n        if actor.region != self.lifecycle.REGION:\n            raise PermissionError("forgetting memory requires a Memory/Context identity")\n        if not reason:\n            raise ValueError("forgetting requires an explicit reason")\n\n        content_digest = canonical_digest({"memory_id": row.memory_id, "text": row.text})\n        existing = self._tombstones.get(row.memory_id)\n        if existing is not None:\n            self._validate_tombstone_semantics(existing)\n            return existing\n\n        if evidence is None:\n            raise PermissionError("first-time forgetting requires actual evidence and a preissued learning evidence lease")\n        self.registry.get(evidence.verifier_agent_id)\n        if authority_lease_id is None or not str(authority_lease_id).strip():\n            raise PermissionError("first-time forgetting requires a preissued learning evidence lease")\n        subject_digest = self.forget_subject_digest(\n            row.memory_id, actor_agent_id=actor.agent_id, reason=reason\n        )\n        authorization = self.learning_authority.consume(\n            str(authority_lease_id),\n            subject_kind="memory",\n            subject_id=row.memory_id,\n            operation_class="memory.forget",\n            producer_agent_id=actor.agent_id,\n            evidence=evidence,\n            subject_digest=subject_digest,\n            use_ref="memory-forget-authority:" + row.memory_id + ":" + subject_digest[:20],\n        )\n        evidence_refs = (evidence.evidence_id,)\n        evidence = _clean_refs(evidence_refs)\n'''
replace_once(forget_anchor, forget_replacement)

# Remove the now-duplicated content digest / existing-tombstone block from the old body.
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

# Allow restore to validate v0.0.12 authority linkage without minting/re-consuming capabilities.
replace_once(
    '''    def from_state(\n        cls,\n        *,\n        registry,\n        events,\n        state: Mapping[str, Any],\n    ) -> "LearningSubstrate":\n''',
    '''    def from_state(\n        cls,\n        *,\n        registry,\n        events,\n        state: Mapping[str, Any],\n        learning_authority: LearningEvidenceAuthority | None = None,\n    ) -> "LearningSubstrate":\n''',
)
replace_once(
    '''        result = cls(\n            registry=registry,\n            events=events,\n            memory=memory,\n            lifecycle=lifecycle,\n            relations=relations,\n            skills=skills,\n            experiences=experiences,\n        )\n''',
    '''        result = cls(\n            registry=registry,\n            events=events,\n            memory=memory,\n            lifecycle=lifecycle,\n            relations=relations,\n            skills=skills,\n            experiences=experiences,\n            learning_authority=learning_authority,\n        )\n''',
)

# Insert v0.0.12 forget authority linkage validation at the end of existing forget ledger semantics.
needle = '''            if tombstone.forget_receipt_id != receipt.receipt_id:\n                raise ValueError("memory tombstone forget receipt authority mismatch")\n'''
replacement = needle + '''            if receipt.authorization_use_receipt_id is not None:\n                if tombstone.authorization_use_receipt_id != receipt.authorization_use_receipt_id:\n                    raise ValueError("memory tombstone authorization use receipt mismatch")\n                authority = self.learning_authority\n                try:\n                    use = next(\n                        row\n                        for lease_state in authority.to_state().get("leases", ())\n                        for row in authority.uses_for(str(lease_state["lease_id"]))\n                        if row.receipt_id == receipt.authorization_use_receipt_id\n                    )\n                except StopIteration as exc:\n                    raise ValueError("memory forget authorization use receipt is missing") from exc\n                if (\n                    use.subject_kind != "memory"\n                    or use.subject_id != receipt.memory_id\n                    or use.operation_class != "memory.forget"\n                    or use.producer_agent_id != receipt.actor_agent_id\n                    or use.evidence_id not in receipt.evidence_refs\n                ):\n                    raise ValueError("memory forget authorization receipt does not match exact forgetting authority")\n'''
replace_once(needle, replacement)

PATH.write_text(text, encoding="utf-8")
print("patched", PATH)
