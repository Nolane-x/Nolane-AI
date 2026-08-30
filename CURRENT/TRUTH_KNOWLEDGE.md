# Truth / Knowledge — A-layer canonical semantics

Status: candidate architecture on `feat/truth-knowledge-a-hardening`.

## Scope

This document owns only External Core family A:

`Evidence -> Knowledge -> Epistemic -> Verification -> Assurance`

It does not take authority from Memory/Learning, Candidate Synthesis, Capability Acquisition, Planning, Execution, Coding, Organization coordination, or `nolane.evaluation`.

## Separation invariant

The five stages are independently bounded semantic authorities. No stage may silently perform the next stage's decision.

1. **Evidence** records immutable observations with explicit provenance, source family, channel and polarity. Revocation is a tombstone; historical evidence is never rewritten or deleted.
2. **Knowledge** owns proposition identity, evidence references and derivation lineage. It does not decide whether a proposition is true.
3. **Epistemic** owns uncertainty and contradiction. `UNKNOWN`, `SUPPORTED`, `REFUTED`, and `CONTRADICTED` are explicit states. Derived claims cannot remain supported if a parent is no longer supported.
4. **Verification** owns independent challenge receipts bound to the exact Knowledge + Epistemic state. Negative results remain in the ledger. Correlated mirrors sharing one source family count as one independent source.
5. **Assurance** owns final closure only. Strict closure consumes a canonical `EpistemicSnapshot`; it cannot accept caller-asserted epistemic state as equivalent authority.

## Canonical pipeline

```text
TruthEvidence / EvidenceRevocation
        |
        v
KnowledgeClaim + derivation DAG
        |
        v
EpistemicSnapshot
  - claim assessments
  - contradiction records
  - epistemic debt
        |
        v
TruthVerificationReceipt[]
  - exact knowledge digest
  - exact epistemic snapshot digest
  - verifier/source family
  - channel
  - positive or negative result
        |
        v
TruthClosureCertificate
```

## Evidence invariants

- IDs are immutable; same-ID rebinding fails closed.
- Evidence carries a content digest over semantic identity/provenance.
- `source_id` and `source_family` are distinct so mirrors can be recognized as correlated.
- Channel is explicit (`observation`, `test`, `reproduction`, `adversarial`, `audit`, `external`).
- Polarity is explicit (`support`, `refute`, `neutral`).
- Revocation does not mutate the original evidence record.
- Restore recomputes content identity and rejects tampered evidence/revocation state.

The historical `nolane.external_core.evidence.EvidenceRecord` remains compatibility authority for existing execution/evaluation flows. `evidence_truth` is additive and does not change that public contract.

## Knowledge invariants

`nolane.external_core.knowledge` is a new canonical semantic boundary.

- A claim is a content-addressed proposition: `(claim_id, subject, relation, object, risk, evidence_ids, parent_claim_ids)`.
- Parent claims must already exist; this construction rule keeps the derivation graph acyclic without trusting serialized graph metadata.
- Evidence lifecycle cannot rewrite Knowledge identity.
- Evidence revocation or absence marks directly dependent claims impacted and propagates transitively to descendants.
- Same-ID claim rebinding fails closed.
- Restore recomputes every claim digest.

Risk classes are `LOW`, `STANDARD`, `HIGH`, `CRITICAL` and control downstream verification diversity; they do not alter proposition identity after creation.

## Epistemic invariants

Epistemic state is a judgment over exact Evidence + Knowledge state, not a second knowledge store.

- Missing/revoked support produces `UNKNOWN`, never an implicit false or true.
- Support and refutation together produce `CONTRADICTED`; neither side is discarded.
- A derived claim becomes `UNKNOWN` whenever any parent is not `SUPPORTED`.
- Separately supported propositions with the same `(subject, relation)` and different objects are retained as an `EpistemicContradiction` rather than winner-take-all overwrite.
- Unresolved unknowns/contradictions create explicit epistemic debt.
- Critical-claim debt is marked critical and can veto Assurance.
- `EpistemicSnapshot` binds Knowledge digest, Evidence digest, all assessments, all contradictions and all debt into one deterministic digest.

The historical `EpistemicWorkspace` remains compatibility-preserving and is not silently widened into Knowledge authority.

## Verification invariants

A `TruthVerificationReceipt` binds:

- claim ID,
- verifier identity,
- source family,
- verification channel,
- positive/negative result,
- exact Knowledge digest,
- exact Epistemic snapshot digest,
- referenced evidence IDs.

Rules:

- stale receipts cannot verify a changed Knowledge/Epistemic state;
- negative receipts are append-only evidence and are never filtered from history;
- a receipt-ID collision with changed semantics fails closed;
- independent-source coverage counts unique source families, not raw verifier count;
- channel diversity is measured independently from source-family diversity;
- restore recomputes receipt identity and rejects tampering.

The existing neural-candidate `VerificationAuthority` remains unchanged.

## Assurance invariants

`TruthAssuranceGate.close_snapshot()` is the authoritative strict path.

It requires:

- Knowledge digest exactly matches the snapshot's Knowledge binding;
- target claim is `SUPPORTED` in that snapshot;
- target claim is not a member of an unresolved competing-proposition contradiction;
- no critical epistemic debt applies to the claim;
- all considered verification receipts are bound to that exact Knowledge + Epistemic state;
- no bound negative verification exists;
- risk-specific independent-source and channel diversity thresholds pass.

Current minimum diversity policy:

| Risk | independent source families | distinct channels |
| --- | ---: | ---: |
| LOW | 1 | 1 |
| STANDARD | 1 | 1 |
| HIGH | 2 | 2 |
| CRITICAL | 3 | 3 |

A closure certificate is content-addressed over the exact state bindings, receipt IDs, debt IDs, disposition and reasons. Restore recomputes the certificate digest.

The existing general `AssuranceControlPlane` remains unchanged; truth closure is additive rather than a hidden widening of software/promotion Assurance semantics.

## Nolane World adversarial transfer

The design deliberately transfers only architecture-compatible invariants from Nolane World 0.12.0's epistemic substrate:

- first-class unknowns and contradictions;
- revocation reopens dependencies;
- source mirrors do not manufacture independence;
- unresolved critical epistemic debt blocks closure;
- high-risk closure requires independent channels;
- negative trials/results remain visible;
- state/certificates are content-bound;
- fake or unbound coverage must fail closed.

Nolane World is used as an adversarial reasoning harness, not copied as a replacement architecture.

## Compatibility and rollout

This candidate is additive. Existing public APIs in `evidence.py`, `epistemic.py`, `verification.py`, and `assurance.py` are left intact so concurrent B/C/etc workstreams are not forced through a cross-domain migration.

The next safe cutover after acceptance is adapter-based: existing evidence chunks can be projected into Truth Evidence + Knowledge claims and compared against legacy `EpistemicWorkspace` behavior before any authority migration. A cutover must not make the legacy parser an implicit Knowledge owner again.

## Acceptance contracts

The dedicated `Truth Knowledge A Layer` workflow compiles all new boundaries and runs focused contracts on Python 3.11 and 3.13. The contracts cover:

- content-addressed Knowledge and revocation propagation;
- correlated-source independence;
- first-class unknown/contradiction;
- negative-result retention;
- risk-sensitive closure;
- same-ID collision rejection;
- competing supported proposition preservation;
- parent-refutation propagation;
- canonical snapshot Assurance binding;
- fail-closed restore/tamper rejection.
