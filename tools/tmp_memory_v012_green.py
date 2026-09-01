from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    target.write_text(text.replace(old, new, 1))


# Production: superseding becomes effective only after the replacement
# has crossed the explicit verified-admission authority boundary.
replace_once(
    "nolane/memory/learning_substrate.py",
    '''        self._metadata[row.memory_id] = replace(
            metadata,
            epistemic_type=EpistemicType.VERIFIED,
            last_verified_ref=evidence.evidence_id,
            source_refs=tuple(sorted(set(metadata.source_refs + (evidence.evidence_id,)))),
        )
        return self.memory.get(row.memory_id)
''',
    '''        self._metadata[row.memory_id] = replace(
            metadata,
            epistemic_type=EpistemicType.VERIFIED,
            last_verified_ref=evidence.evidence_id,
            source_refs=tuple(sorted(set(metadata.source_refs + (evidence.evidence_id,)))),
        )
        admitted = self.memory.get(row.memory_id)
        if admitted.supersedes is not None:
            incumbent = self.memory.get(admitted.supersedes)
            if incumbent.status is MemoryStatus.ACTIVE:
                self.lifecycle.transition(
                    incumbent.memory_id,
                    actor_agent_id=actor.agent_id,
                    new_status=MemoryStatus.SUPERSEDED,
                    reason=f"superseded by {admitted.memory_id}",
                    evidence_refs=(evidence.evidence_id,),
                    correction_ref=use.receipt_id,
                )
        return self.memory.get(row.memory_id)
''',
)

# Production: a VERIFIED-source compaction is still an unadmitted HYPOTHESIS
# candidate until its own independent verification lease is consumed.
replace_once(
    "nolane/memory/learning_substrate.py",
    '''        receipt = MemoryCompactionReceipt(
            source_memory_ids=source_ids,
            compacted_memory_id=compacted.memory_id,
            source_digest=self._compaction_source_digest(source_ids),
            epistemic_type=epistemic_type.value,
            actor_agent_id=actor,
            evidence_refs=evidence,
            compacted_digest=self._compaction_target_digest(compacted.memory_id),
        )
''',
    '''        compacted_epistemic_type = self.metadata(compacted.memory_id).epistemic_type
        receipt = MemoryCompactionReceipt(
            source_memory_ids=source_ids,
            compacted_memory_id=compacted.memory_id,
            source_digest=self._compaction_source_digest(source_ids),
            epistemic_type=compacted_epistemic_type.value,
            actor_agent_id=actor,
            evidence_refs=evidence,
            compacted_digest=self._compaction_target_digest(compacted.memory_id),
        )
''',
)
replace_once(
    "nolane/memory/learning_substrate.py",
    '''        epistemic_type = next(iter(epistemic_types))
        if receipt.epistemic_type != epistemic_type.value or compacted_metadata.epistemic_type is not epistemic_type:
            raise ValueError("memory compaction restore epistemic type mismatch")
''',
    '''        source_epistemic_type = next(iter(epistemic_types))
        expected_compacted_epistemic_type = (
            EpistemicType.HYPOTHESIS
            if source_epistemic_type is EpistemicType.VERIFIED
            else source_epistemic_type
        )
        if (
            receipt.epistemic_type != expected_compacted_epistemic_type.value
            or compacted_metadata.epistemic_type is not expected_compacted_epistemic_type
        ):
            raise ValueError("memory compaction restore epistemic type mismatch")
''',
)

# Historical helpers: choose a registered verifier that is independent from the
# producer/actor; test stubs and the canonical first-generation runtime differ.
helper = Path("tests/memory_learning_authority_helpers.py")
text = helper.read_text()
old = '''def admit_memory(
    substrate,
    memory_or_id,
    *,
    evidence_id: str,
    actor_agent_id: str = "memory.chief",
    verifier_agent_id: str = "memory.worker",
):
    memory_id = str(getattr(memory_or_id, "memory_id", memory_or_id))
    row = substrate.memory.get(memory_id)
    evidence = clean_evidence(evidence_id, verifier_agent_id=verifier_agent_id)
'''
new = '''def _registered_independent_verifier(substrate, producer_agent_id: str, preferred: str | None = None) -> str:
    candidates = (
        preferred,
        "memory.worker",
        "memory.chief",
        "memory.lifecycle.01",
        "memory.context-compiler.01",
        "memory.knowledge-graph.01",
        "verification.unit-property.01",
        "verification.chief",
    )
    for candidate in candidates:
        if candidate is None or str(candidate) == str(producer_agent_id):
            continue
        try:
            substrate.registry.get(str(candidate))
        except KeyError:
            continue
        return str(candidate)
    raise KeyError("no registered independent verifier is available for historical Memory/Learning contract")


def admit_memory(
    substrate,
    memory_or_id,
    *,
    evidence_id: str,
    actor_agent_id: str = "memory.chief",
    verifier_agent_id: str | None = None,
):
    memory_id = str(getattr(memory_or_id, "memory_id", memory_or_id))
    row = substrate.memory.get(memory_id)
    verifier_agent_id = _registered_independent_verifier(
        substrate, row.owner_agent_id, verifier_agent_id
    )
    evidence = clean_evidence(evidence_id, verifier_agent_id=verifier_agent_id)
'''
if text.count(old) != 1:
    raise SystemExit("helper admit verifier snippet did not match exactly once")
text = text.replace(old, new, 1)
old = '''    actor_agent_id = str(actor_agent_id)
    if verifier_agent_id is None:
        verifier_agent_id = "memory.chief" if actor_agent_id == "memory.worker" else "memory.worker"
    evidence = clean_evidence(evidence_id, verifier_agent_id=verifier_agent_id)
'''
new = '''    actor_agent_id = str(actor_agent_id)
    verifier_agent_id = _registered_independent_verifier(
        substrate, actor_agent_id, verifier_agent_id
    )
    evidence = clean_evidence(evidence_id, verifier_agent_id=verifier_agent_id)
'''
if text.count(old) != 1:
    raise SystemExit("helper forget verifier snippet did not match exactly once")
helper.write_text(text.replace(old, new, 1))

# Historical compaction expectation: verified sources produce a candidate, not a
# self-certified verified summary.
replace_once(
    "tests/test_memory_learning_adaptive_policy_v005.py",
    '''    assert substrate.metadata(compacted.memory_id).epistemic_type is EpistemicType.VERIFIED
    assert substrate.memory.get(first.memory_id).status is MemoryStatus.ACTIVE
''',
    '''    assert substrate.metadata(compacted.memory_id).epistemic_type is EpistemicType.HYPOTHESIS
    assert substrate.memory.get(compacted.memory_id).status is MemoryStatus.QUARANTINED
    assert receipt.epistemic_type == EpistemicType.HYPOTHESIS.value
    assert substrate.memory.get(first.memory_id).status is MemoryStatus.ACTIVE
''',
)

# Digest invariant should be exercised across a legal lifecycle-only change from
# an unadmitted compaction candidate.
replace_once(
    "tests/test_memory_learning_compaction_target_v008.py",
    '''    substrate.decay_memory(
        compacted.memory_id,
        actor_agent_id="memory.worker",
        reason="freshness window elapsed",
        evidence_refs=("freshness-observation",),
    )
''',
    '''    substrate.lifecycle.transition(
        compacted.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.CONTRADICTED,
        reason="later contradictory observation",
        evidence_refs=("contradiction-observation",),
    )
''',
)
replace_once(
    "tests/test_memory_learning_compaction_target_v008.py",
    '''    assert restored.memory.get(compacted.memory_id).status is MemoryStatus.STALE
''',
    '''    assert restored.memory.get(compacted.memory_id).status is MemoryStatus.CONTRADICTED
''',
)

# Snapshot tamper now fails earlier at lifecycle-history consistency, which is a
# stronger fail-closed invariant than the later tombstone check.
replace_once(
    "tests/test_memory_learning_retrieval_snapshot_authority_v009.py",
    '''    with pytest.raises(ValueError, match="memory tombstone requires archived lifecycle authority"):
''',
    '''    with pytest.raises(ValueError, match="restored memory status disagrees with lifecycle history"):
''',
)

# Explicit admission adds a lifecycle receipt. Forgetting an already archived
# memory must reuse the existing archive transition and add no new lifecycle row.
replace_once(
    "tests/test_memory_learning_tombstone_authorization_v010.py",
    '''    tombstone = forget_memory(substrate, row.memory_id, actor_agent_id="memory.chief", reason="later governed forgetting", evidence_id='forget-proof')

    assert tombstone.actor_agent_id == "memory.chief"
''',
    '''    receipts_before_forget = substrate.lifecycle.receipts_for(row.memory_id)
    tombstone = forget_memory(substrate, row.memory_id, actor_agent_id="memory.chief", reason="later governed forgetting", evidence_id='forget-proof')

    assert tombstone.actor_agent_id == "memory.chief"
''',
)
replace_once(
    "tests/test_memory_learning_tombstone_authorization_v010.py",
    '''    assert substrate.lifecycle.receipts_for(row.memory_id) == (archive,)
''',
    '''    assert receipts_before_forget[-1] == archive
    assert substrate.lifecycle.receipts_for(row.memory_id) == receipts_before_forget
''',
)
