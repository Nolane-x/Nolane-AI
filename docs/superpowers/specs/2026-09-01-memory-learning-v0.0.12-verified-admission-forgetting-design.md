# Memory/Learning v0.0.12 — Verified Admission & Irreversible Forget Authorization

## Boundary

This closure preserves the existing Family-B authority graph and adds no new authority plane. `LearningEvidenceAuthority` remains the sole subject-bound evidence capability ledger for learning mutations.

## Verified admission

New memory content is remembrance, not belief. Caller-supplied evidence-reference strings cannot make a new memory usable as verified truth. A verified admission must consume a clean, externally verified, single-use lease bound to the exact memory content, owner/scope, metadata, lifecycle state, and proposed `memory.verify` transition. The authority use receipt is retained as lifecycle corrective authority so restore can audit the transition.

## Irreversible forgetting

The first irreversible transition toward forgetting must be authorized before archival. A `memory.forget` lease binds the exact current memory state, metadata/lifecycle state, Memory/Context actor, and reason. The use receipt is persisted into the forget receipt and tombstone. Cross-memory reuse, changed reason, stale state, evidence rebinding, replay, and forged restore linkage fail closed.

## Compatibility

Historical state replay remains explicit and must not mint new authority. Runtime composition continues to restore one shared `LearningEvidenceAuthority` and rebind it to B consumers. Existing historical tests are changed only where they are callers of an intentionally tightened production contract.

## Verification

TDD RED precedes implementation. Acceptance requires the Memory/Learning 3.11/3.13 matrix plus full Refoundation and integrity regressions on the exact latest-main integrated tree.
