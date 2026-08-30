# A8 Canonical Dependency-Scoped Truth Binding Design

Status: approved for implementation on `refoundation/truth-knowledge-a8-scoped-binding`.

## Problem

A1–A7 intentionally chose conservative whole-ledger state binding. `EpistemicSnapshot` binds the complete Knowledge and Evidence ledgers, Truth Verification receipts bind the complete Knowledge digest plus the complete epistemic snapshot digest, and Assurance certificates bind complete Knowledge, Evidence, Epistemic and Verification digests. This is correct but unnecessarily invalidates a truth closure when unrelated facts or verification receipts are appended elsewhere in the ledgers.

A8 must reduce invalidation to the semantic dependency neighborhood of one target claim without weakening contradiction, provenance, ancestor, revocation, negative-verification, epistemic-debt, or live-authority guarantees.

## Goals

1. A truth closure survives mutations that are provably unrelated to its target dependency neighborhood.
2. Direct target evidence changes, ancestor changes, competing propositions, revocation, relevant epistemic debt and relevant negative verification still invalidate or block closure.
3. A contradiction involving the target or any transitive ancestor blocks descendant closure.
4. Scope membership is derived from live canonical ledgers and cannot be caller-declared authority.
5. V1 global state receipts/certificates remain deserializable and auditable.
6. V2 scoped issuance is additive under the existing five canonical A authorities and creates no sixth component/helper authority.
7. A1–A7 contracts remain green.

## Non-goals

- No ownership changes for Memory/Learning, Reasoning/Invention, Goal/Design, Acting, Software Engineering, Infrastructure, Organization, or Evaluation.
- No replacement of the existing canonical `external.knowledge`, `external.epistemic`, `external.verification`, or `external.assurance` modules.
- No probabilistic truth scoring, source reputation model, or new risk policy.
- No deletion or reinterpretation of historical v1 certificates/receipts.
- No attempt to make a scoped certificate valid forever: relevant live state changes must still invalidate it.

## Authority model

The canonical authorities remain exactly:

- `external.evidence` -> `nolane.external_core.evidence`
- `external.knowledge` -> `nolane.memory.knowledge`
- `external.epistemic` -> `nolane.external_core.epistemic`
- `external.verification` -> `nolane.external_core.verification`
- `external.assurance` -> `nolane.external_core.assurance`

A8 extends the already-bound helpers `knowledge_truth.py`, `epistemic_truth.py`, `verification_truth.py`, and `assurance_truth.py`. It does not add `COMPONENT_ID`, a sixth Truth helper binding, or a new registry row. `TruthDependencyScope` is a record and derivation mechanism inside the existing `external.epistemic` Truth helper.

## Canonical dependency closure

For target claim `T`, two claim sets are derived.

### Lineage set

`lineage(T)` is `T` plus every transitive `parent_claim_id` reachable from `T`.

### Scope set

`scope(T)` is a fixed point:

1. Seed with `lineage(T)`.
2. For every claim currently in scope, add every claim in Knowledge having the same `(subject, relation)` regardless of object value. These are potential competing propositions.
3. For every newly added claim, add all of its transitive parents.
4. Repeat steps 2–3 until no new claim is added.

This fixed point is required. Merely including target parents would miss a newly introduced competitor; including competitors without their parents would mis-evaluate whether those competitors are epistemically supported.

All claim-ID collections are sorted unique sets before identity computation.

## Scoped state projection

`TruthDependencyScope` is content-addressed and includes sufficient canonical projections to make relevant state changes visible while excluding unrelated ledger rows.

It contains at minimum:

- schema identifier;
- target claim ID;
- canonical lineage claim IDs;
- canonical full scope claim IDs;
- scoped Knowledge projection digest over exact `KnowledgeClaim.to_state()` rows for scope claims;
- scoped Evidence projection digest over every evidence ID referenced by scope claims, including explicit missing/active/revoked state and exact record/revocation content;
- scoped Epistemic projection over assessments for scope claims;
- contradictions whose claim set intersects the scope;
- epistemic debts whose claim belongs to the scope;
- the final scope digest.

The scope is reconstructed from live Knowledge and Evidence. `from_state()` proves content/serialization integrity only. Any consumer relying on it must compare it to a fresh canonical scope derived from live authorities.

## Contradiction and debt propagation

A8 does not rewrite the global epistemic disposition model. Individual claims may remain `SUPPORTED` while a first-class `EpistemicContradiction` records a competing proposition.

For strict descendant closure:

- if any unresolved contradiction contains the target or any claim in `lineage(T)`, closure is blocked with an ancestor/target conflict reason;
- critical epistemic debt attached to the target or any claim in `lineage(T)` blocks descendant closure;
- if an ancestor is no longer `SUPPORTED`, the existing parent-state rule continues to make the derived claim unsupported.

Contradictions/debts outside the canonical scope cannot affect the certificate. Contradictions/debts inside competitor-only lineage are represented in the scope digest and therefore can change scope identity, but the direct veto applies to the target lineage.

## Scoped Evidence projection

Evidence projection is derived from evidence IDs referenced by scope claims, not from every ledger record.

For every referenced evidence ID the projection includes one canonical row:

- missing: the ID plus `status = missing`;
- active: exact `TruthEvidence.to_state()` plus `status = active`;
- revoked: exact evidence record plus exact revocation row plus `status = revoked`.

Therefore:

- unrelated evidence append/revocation does not change a target scope;
- direct or ancestor evidence revocation does;
- missing evidence remains visible as epistemic debt;
- cross-subject evidence remains present but cannot become support because existing subject binding remains authoritative.

## Verification binding v2

`TruthVerificationReceipt` remains one compatibility type and must preserve exact v1 serialization/digests for v1 rows.

A8 adds a scoped binding mode. A scoped receipt binds:

- target claim ID;
- verifier identity and source family;
- channel and pass/fail result;
- canonical `scope_digest`;
- cited evidence IDs.

It does not include whole-ledger Knowledge/Epistemic digests in its v2 content identity.

The ledger gains scoped lookup/coverage methods. Provenance validation remains unchanged: cited evidence must be active, belong to the receipt claim, and match verifier identity, family, and channel.

The canonical verification projection digest for a target is computed only from scoped receipts for that target bound to the current `scope_digest`. Thus unrelated receipts do not stale a scoped certificate, while adding a new relevant current-scope receipt does.

Legacy v1 `bound_receipts()` and v1 restore remain unchanged.

## Assurance binding v2

`TruthAssuranceGate.close_live()` becomes the canonical dependency-scoped issuance path.

It must:

1. derive a fresh canonical `TruthDependencyScope` from live Knowledge/Evidence;
2. use the canonical target assessment;
3. veto target/ancestor contradiction;
4. veto critical target/ancestor debt;
5. evaluate only current-scope verification coverage;
6. preserve the existing risk-specific source-family/channel diversity policy;
7. veto relevant negative verification;
8. issue a v2 certificate bound to `scope_digest` plus the scoped verification projection digest.

`close_snapshot()` remains a strict v1 compatibility issuance path so historical tests and callers are not silently reinterpreted. It stays globally bound and therefore conservative.

`validate_certificate()` dispatches by certificate binding mode:

- v1 certificate: re-derive through the v1 compatibility path;
- v2 certificate: re-derive through current `close_live()` scoped issuance and require exact certificate equality.

A digest-valid self-issued v2 certificate therefore has no authority without live revalidation.

## Certificate compatibility

`TruthClosureCertificate` remains one compatibility type. V1 payload shape and digest must remain byte-semantically unchanged for old serialized states.

V2 adds an explicit scoped binding mode and scoped state fields. V2 identity must not include whole-ledger digests, otherwise unrelated ledger changes would reintroduce A7's scalability limitation.

V1 and v2 state parsing must reject ambiguous mixed-mode rows, duplicate set-semantic IDs, malformed binding mode, and inconsistent decision/reason combinations.

## Required adversarial contracts

A8 is not accepted unless tests prove all of the following:

1. Adding unrelated Knowledge and Evidence leaves a previously issued v2 certificate valid.
2. Revoking target evidence invalidates the certificate.
3. Revoking ancestor evidence invalidates a descendant certificate.
4. Adding a supported competing proposition for the target invalidates/blocks closure.
5. Adding a supported competing proposition for an ancestor invalidates/blocks descendant closure.
6. Adding unrelated Verification receipts leaves the target certificate valid.
7. A negative current-scope target verification invalidates/blocks closure.
8. Cross-subject evidence cannot become scoped support.
9. Scope identity is independent of claim/evidence insertion order.
10. A serialized scope with omitted ancestor, competitor, or referenced evidence cannot be trusted after live canonical revalidation.
11. Different dependency graphs produce different scoped identities.
12. Caller-forged scope state cannot be used for strict issuance.
13. A1–A7 tests remain green unchanged.
14. Refoundation Epoch 0 and repository authority audits remain green.

## Acceptance and rollout

A8 is complete only when:

- RED proof demonstrates the whole-ledger invalidation problem and ancestor-conflict gap on the A7 baseline;
- GREEN proof passes all `tests/test_truth_knowledge_*.py` on Python 3.11 and 3.13;
- Refoundation Epoch 0 passes both supported Python versions including 67/67 dossier freshness, repository audit, zero-loss evidence, organization/campaign/execution regressions, and frozen Neural checks;
- the PR diff remains scoped to family A Truth protocol code/tests/docs/required workflow metadata;
- there are no unresolved review threads or authority duplicates.
