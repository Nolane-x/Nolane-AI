# Memory/Learning v0.0.12 — Verified Admission + Forget Authorization

## Scope

Close two remaining Family-B trust bypasses without creating a second authority plane:

1. A caller-supplied non-empty `evidence_ids` list must not make a new memory `ACTIVE + VERIFIED`.
2. First-time irreversible forgetting must require a pre-issued, exact-state-bound, single-use `LearningEvidenceAuthority` lease before archival/tombstoning begins.

Skill Forge proof-carrying promotion remains out of scope for this wave.

## Task 1 — Verified memory admission

- Add RED contracts proving verified-looking string refs remain quarantined.
- Bind `memory.verify` to exact current memory + metadata + lifecycle state and actual clean external `EvidenceRecord`.
- Consume one single-use learning-evidence lease before activation.
- Store the authority-use receipt as the lifecycle corrective authority and reject stale/cross-memory/replayed leases.
- Ensure retrieval cannot select unadmitted memory.
- Preserve deterministic restore and legacy historical replay where explicitly required by existing state contracts.

## Task 2 — Irreversible forgetting authorization

- Add RED contracts proving first-time `forget()` cannot execute without a pre-issued lease.
- Bind `memory.forget` to exact current memory + metadata + lifecycle state + actor + reason.
- Consume authority before the first irreversible lifecycle mutation.
- Bind `MemoryForgetReceipt` and `MemoryTombstone` to the exact learning-authority use receipt.
- Reject cross-memory, stale-state, changed-reason, replay, and forged restore linkage.
- Preserve authority/forget/tombstone lineage through full runtime snapshot/restore.

## Verification

- Focused v0.0.12 contracts RED before production changes.
- Focused GREEN after the minimal implementation.
- Memory/Learning matrix on Python 3.11 and 3.13.
- Refoundation Epoch-0, E-Acting regression, R1.9 and R2.0i integrity gates.
- Exact latest-main reconciliation before merge; no force-push and no unrelated Family A/C/D/E/F changes.
