# Truth / Knowledge — External Core A

Status: Refoundation hardening candidate on `refoundation/truth-knowledge-a-hardening`.

## Authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

The Truth Closure implementation is an additive protocol under those authorities, not a second component registry:

- `evidence_truth.py` has `PARENT_COMPONENT_ID = "external.evidence"`;
- `knowledge_truth.py` has `PARENT_COMPONENT_ID = "external.knowledge"`;
- `epistemic_truth.py` has `PARENT_COMPONENT_ID = "external.epistemic"`;
- `verification_truth.py` has `PARENT_COMPONENT_ID = "external.verification"`;
- `assurance_truth.py` has `PARENT_COMPONENT_ID = "external.assurance"`.

Protocol helpers must never declare `COMPONENT_ID`. Canonical component identity belongs only to the repository component registry and its accepted canonical-native modules.

The protocol uses `nolane.core.canonical_digest.canonical_digest`; it does not introduce a private digest authority.

## Truth-closure pipeline

```text
canonical external.evidence
        |
        +-- TruthEvidence / EvidenceRevocation
        v
canonical external.knowledge
        |
        +-- KnowledgeClaim + derivation DAG
        v
canonical external.epistemic
        |
        +-- EpistemicSnapshot
        |     - UNKNOWN / SUPPORTED / REFUTED / CONTRADICTED
        |     - competing propositions
        |     - epistemic debt
        v
canonical external.verification
        |
        +-- TruthVerificationReceipt[]
        |     - exact knowledge state
        |     - exact epistemic state
        |     - live evidence provenance
        v
canonical external.assurance
        |
        +-- TruthClosureCertificate
```

No stage may silently perform the next stage's decision.

## Evidence protocol invariants

- Evidence identity, subject, source identity, source family, channel, polarity and payload digest are explicit.
- Same evidence ID with changed semantics fails closed.
- One source identity cannot be rebound to multiple source families inside the ledger.
- Revocation is append-only admissibility state; the original evidence record is retained.
- Restore recomputes content identity and rejects tampered evidence or revocation state.
- Cross-subject evidence cannot support another claim merely because its evidence ID is referenced.

## Knowledge protocol invariants

- `external.knowledge` remains the existing canonical reusable knowledge fabric in `nolane.memory.knowledge`.
- `knowledge_truth.py` adds proposition/derivation semantics needed by truth closure; it does not replace retrieval/document/chunk authority.
- A truth claim is content-addressed over `(claim_id, subject, relation, object, risk, evidence_ids, parent_claim_ids)`.
- Parent references form a DAG; cycles and missing parents fail closed.
- Restore is topological and independent of serialized claim-ID sort order.
- Evidence lifecycle never rewrites knowledge identity; invalidated evidence marks dependent claims impacted and propagates to descendants.

## Epistemic protocol invariants

- Epistemic judgment is recomputed from exact Knowledge + Evidence state.
- Missing or revoked support produces `UNKNOWN`, never implicit truth or falsehood.
- Support plus refutation produces `CONTRADICTED`; neither side is discarded.
- A derived claim cannot stay supported when a parent is no longer `SUPPORTED`.
- Separately supported claims sharing `(subject, relation)` but disagreeing on object remain explicit competing propositions.
- Missing, revoked or cross-subject evidence generates epistemic debt.
- Critical unresolved debt can veto Assurance.
- `EpistemicSnapshot` is content-addressed and tamper-evident.

## Verification protocol invariants

A `TruthVerificationReceipt` binds:

- claim ID;
- verifier/source identity;
- source family;
- verification channel;
- pass/fail result;
- exact Knowledge digest;
- exact Epistemic snapshot digest;
- cited evidence IDs.

Raw receipts remain audit history. Only provenance-valid receipts count toward strict Assurance. A counted receipt must cite active evidence for the same claim whose source identity, source family and channel match the receipt. Negative receipts are retained. Correlated mirrors sharing one source family count as one independent source.

## Assurance protocol invariants

`TruthAssuranceGate.close_snapshot()` and `close_live()` are the strict paths.

Strict closure requires:

- the snapshot Knowledge digest equals the live Knowledge digest;
- the snapshot Evidence digest equals the live Evidence digest;
- Assurance recomputation produces the same canonical Epistemic snapshot;
- the target claim is `SUPPORTED` and not in an unresolved competing-proposition contradiction;
- no critical epistemic debt applies;
- verification coverage is exact-state-bound and live-provenance-valid;
- no bound negative verification exists;
- risk-specific independent source-family and channel diversity requirements pass.

Current minimum diversity policy:

| Risk | independent source families | distinct channels |
| --- | ---: | ---: |
| LOW | 1 | 1 |
| STANDARD | 1 | 1 |
| HIGH | 2 | 2 |
| CRITICAL | 3 | 3 |

The digest-only legacy `close()` surface is deliberately fail-closed and cannot return an accepted truth certificate.

## Compatibility boundary

The existing canonical APIs remain authoritative for their established duties:

- `EvidenceRecord` for existing verification/evaluation flows;
- `nolane.memory.knowledge` for reusable knowledge retrieval and provenance chunks;
- `EpistemicWorkspace` for the accepted version-aware epistemic workspace;
- `VerificationAuthority` for bounded candidate evaluation/promotion/rollback;
- `AssuranceControlPlane` for policy/domain engineering and promotion assurance.

Truth Closure is additive protocol semantics under those components. Any future integration into their public surfaces must be adapter-based and contract-tested; protocol helpers may not seize canonical component identity.

## Adversarial hardening waves

- **A1**: introduced explicit Evidence → Knowledge → Epistemic → Verification → Assurance truth semantics.
- **A2**: added competing-proposition preservation, parent-state propagation, canonical snapshots and tamper-resistant restore.
- **A3**: attacked cross-subject evidence laundering, source-family rebinding, stale snapshot replay, forged snapshots, ungrounded verification, legacy closure bypass and restore-order failure.
- **A4**: discovered and forbids duplicate canonical authority, removes the private truth digest, moves proposition semantics to `knowledge_truth.py`, and binds every helper to one existing canonical parent component.

## Acceptance gates

The dedicated `Truth Knowledge A Layer` workflow runs on Python 3.11 and 3.13 and must:

1. compile the five canonical A authorities plus all Truth Closure protocol modules;
2. pass A1/A2/A3/A4 truth contracts;
3. pass repository authority projection audit.

The Refoundation Epoch 0 workflow remains the broader repository regression gate. Historical R-series workflows do not define current architecture authority.
