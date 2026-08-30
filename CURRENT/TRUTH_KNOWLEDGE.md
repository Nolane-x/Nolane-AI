# Truth / Knowledge — External Core A

Status: **Refoundation A1–A8 accepted Truth / Knowledge baseline.**

## Canonical authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

Truth Closure is additive protocol semantics beneath those authorities. The helper modules `evidence_truth.py`, `knowledge_truth.py`, `epistemic_truth.py`, `verification_truth.py`, and `assurance_truth.py` must never declare `COMPONENT_ID`. `nolane.metadata.subprotocols` remains a metadata binding registry, not a sixth runtime component. A8 adds no parent authority and no sixth helper binding.

All Truth content identity uses `nolane.core.canonical_digest.canonical_digest`; no private digest authority is permitted.

## A1–A7 accepted baseline

The accepted baseline provides:

- immutable provenance-aware Evidence with source identity/family binding, polarity, channels, append-only revocation, anti-rebinding, anti-cross-subject laundering and tamper-evident restore;
- content-addressed Knowledge propositions with evidence references, derivation DAGs, topological restore, transitive invalidation and canonical set ordering;
- first-class Epistemic `UNKNOWN`, `SUPPORTED`, `REFUTED`, `CONTRADICTED`, competing propositions and epistemic debt;
- exact-state Verification receipts, live provenance validation, source-family independence, channel diversity and retained negative results;
- risk-sensitive Assurance, live canonical recomputation and non-self-authenticating closure certificates;
- bidirectional subprotocol ownership metadata without duplicate canonical authority;
- canonical ordering for set-semantic references.

A1–A7 deliberately used whole-ledger Knowledge/Evidence/Epistemic/Verification digests. That maximized invalidation safety but caused unrelated state changes to stale otherwise valid claim closures.

## A8 canonical dependency scope

A8 introduces `truth-dependency-scope-v2` under canonical `external.epistemic` Truth semantics. A `TruthDependencyScope` is a content-addressed state projection derived from live canonical Knowledge and Evidence; it is not caller-declared authority.

For target claim `T`, the scope is a fixed point:

```text
lineage(T)
  = T + every transitive parent

scope(T)
  = fixed_point(
      lineage(T)
      + every claim sharing (subject, relation) with any scoped claim
      + every transitive parent of those competitors
    )
```

The fixed point is mandatory. A target-only scope could hide a competing proposition. A target+parents scope could hide a competitor for an ancestor. A competitor without its own lineage could be judged without the state needed to establish whether it is supported.

`lineage_claim_ids` and `scope_claim_ids` are canonical sorted unique sets.

## Scoped Knowledge projection

`KnowledgeLedger.lineage_claim_ids()` derives target lineage. `KnowledgeLedger.truth_scope_claim_ids()` derives the fixed-point scope. The scoped Knowledge digest contains only exact `KnowledgeClaim.to_state()` rows for the canonical scope claim IDs.

Therefore an unrelated claim append does not change a target scope, while any change in target, ancestor, competitor, or competitor lineage does.

Knowledge ownership does not move: reusable document/chunk/retrieval authority remains `nolane.memory.knowledge`; `knowledge_truth.py` owns only Truth proposition/derivation protocol semantics beneath that parent.

## Scoped Evidence projection

The scoped Evidence projection contains exactly the evidence IDs referenced by scope claims. Every referenced ID has explicit canonical state:

- `missing` — the reference exists but no evidence record exists;
- `active` — exact `TruthEvidence.to_state()`;
- `revoked` — exact evidence record plus exact `EvidenceRevocation.to_state()`.

Consequences:

- unrelated evidence additions/revocations do not stale a target scope;
- target/ancestor/competitor evidence changes do;
- missing/revoked references remain visible;
- cross-subject evidence can remain referenced for audit but cannot become support.

## Scoped Epistemic projection

A8 does not reuse the content digest of global `EpistemicAssessment` inside the scoped identity, because that digest intentionally binds whole-ledger Knowledge/Evidence state. Instead `TruthScopeAssessment` projects only the epistemic semantics relevant to the scoped claim: claim ID, disposition, support evidence IDs and refute evidence IDs.

A `TruthDependencyScope` binds:

- target claim ID;
- lineage claim IDs;
- full fixed-point scope claim IDs;
- referenced evidence IDs;
- scoped Knowledge digest;
- scoped Evidence digest;
- scoped assessments;
- contradictions touching the scope;
- epistemic debts attached to scope claims;
- final canonical scope digest.

`from_state()` proves serialization/content integrity only. `EpistemicJudge.validate_dependency_scope()` recomputes from live canonical ledgers and requires exact equality before a supplied scope can be trusted.

## Lineage conflict and debt law

Global Epistemic semantics continue to preserve competing supported propositions as explicit contradictions rather than overwriting either claim.

For strict A8 descendant closure:

- target disposition must be `SUPPORTED`;
- a contradiction containing the target blocks closure with target-conflict semantics;
- a contradiction containing any transitive ancestor blocks descendant closure with `epistemic_lineage_conflicted`;
- critical debt on the target retains `critical_epistemic_debt` compatibility semantics;
- critical debt on a transitive ancestor blocks descendant closure with `critical_epistemic_lineage_debt`;
- an ancestor that ceases to be `SUPPORTED` continues to make its descendant unsupported through the existing parent-state rule.

Competitor-only debt is retained inside scoped identity but is not independently promoted into a lineage veto unless it affects the target/ancestor lineage under the rules above.

## Verification binding modes

`TruthVerificationReceipt` remains one compatibility type.

### Global v1

A v1 receipt retains its historical payload exactly:

- claim/verifier/source-family/channel/pass state;
- whole Knowledge digest;
- whole Epistemic snapshot digest;
- cited evidence IDs.

No `binding_mode` or `scope_digest` keys are injected into v1 serialized state.

### Dependency-scope v2

A scoped receipt has `binding_mode = dependency-scope-v2` and binds the canonical `scope_digest`. It does not include whole-ledger Knowledge/Epistemic digests in v2 identity. Mixed global+scoped binding state is invalid and fails closed.

`TruthVerificationLedger.coverage_scoped()` applies the same live provenance law as v1: cited evidence must be active, belong to the receipt claim, and match verifier identity, source family and channel. Negative receipts remain retained.

The scoped verification projection digest contains only receipts for the target bound to the exact current scope. Unrelated claim receipts and stale-scope receipts therefore do not change the target verification projection.

## Assurance binding modes

`TruthClosureCertificate` also remains one compatibility type.

### Global v1 compatibility path

`TruthAssuranceGate.close_snapshot()` remains strict whole-ledger v1 issuance. V1 certificate serialization retains its historical payload exactly and remains conservatively stale after unrelated global state changes.

A caller with only historical v1 verification receipts remains on the v1 path when using `close_live()`. A8 does not reinterpret or auto-upgrade v1 receipts as scoped evidence.

### Dependency-scope v2 canonical live path

If a target has scoped verification history, `TruthAssuranceGate.close_live()` derives a fresh canonical dependency scope internally and stays on the v2 path even if relevant state changes make all old scoped receipts stale. This prevents a changed target from silently falling back to v1 and losing scoped conflict/revocation semantics.

V2 closure requires:

- canonical live dependency scope;
- target `SUPPORTED`;
- no target or ancestor conflict veto;
- no target or ancestor critical-debt veto;
- provenance-valid verification bound to the exact current scope;
- no current-scope negative verification;
- unchanged risk-specific independent source-family/channel diversity policy.

Current policy remains:

| Risk | independent source families | distinct channels |
| --- | ---: | ---: |
| LOW | 1 | 1 |
| STANDARD | 1 | 1 |
| HIGH | 2 | 2 |
| CRITICAL | 3 | 3 |

A v2 certificate identity binds the target/risk, `scope_digest`, scoped verification projection digest, relevant receipt IDs, lineage debt IDs, decision and reasons. It intentionally excludes whole-ledger digests.

## Certificate authenticity and validation

Neither v1 nor v2 certificates are self-authenticating authority. A content-valid restored certificate is only a receipt.

`TruthAssuranceGate.validate_certificate()` dispatches by binding mode:

- v1: recompute the current global Epistemic snapshot and re-run strict `close_snapshot()`;
- v2: recompute current dependency scope and scoped live closure through `close_live()`.

Exact certificate equality is required. A digest-valid self-issued or stale certificate cannot acquire authority merely by deserializing successfully.

## Serialization law

- Set-semantic IDs remain sorted and unique before identity computation.
- V1 payloads do not gain v2-only keys.
- V2 receipt/certificate payloads cannot contain v1 global binding fields.
- Unknown/mixed binding modes fail closed.
- Duplicate serialized ledger identities fail closed.
- Content-valid but semantically incomplete scoped state still fails live canonical revalidation.

## Compatibility boundary

The existing canonical APIs remain authoritative for their established duties:

- `EvidenceRecord` for existing evidence/evaluation flows;
- `nolane.memory.knowledge` for reusable knowledge retrieval/provenance chunks;
- `EpistemicWorkspace` for the accepted version-aware workspace;
- `VerificationAuthority` for bounded candidate evaluation/promotion/rollback;
- `AssuranceControlPlane` for policy/domain engineering and promotion assurance.

Truth Closure remains additive protocol semantics. A8 does not seize those public surfaces.

## Hardening lineage

- **A1** — explicit Evidence → Knowledge → Epistemic → Verification → Assurance semantics.
- **A2** — canonical snapshots, parent-state propagation, competing-proposition retention, tamper-resistant restore.
- **A3** — evidence laundering, source-family rebinding, stale replay, forged state, ungrounded verification, legacy bypass and restore-order attacks.
- **A4** — duplicate-authority removal and canonical parent/helper binding.
- **A5** — certificate content integrity separated from live authority authenticity; duplicate serialization fails closed.
- **A6** — bidirectional subprotocol metadata binding without fake parent software revisions.
- **A7** — canonical set ordering / order-malleability closure.
- **A8** — fixed-point dependency-scoped state binding, unrelated-state stability, ancestor conflict/debt propagation and explicit v1/v2 compatibility.

## Acceptance gates

A8 is accepted only if the exact final head passes:

1. Python 3.11 and 3.13 compile for the five canonical A authorities, Truth helpers and metadata registry;
2. every `tests/test_truth_knowledge_*.py` contract, including A1–A8 adversarial/serialization tests;
3. repository authority projection audit with no new migration debt or duplicate authority;
4. full Refoundation Epoch 0 on Python 3.11 and 3.13, including 67/67 dossier freshness, repository audit, zero-loss evidence, organization/campaign/execution regressions and frozen Neural metadata;
5. manual PR scope/review check showing no ownership changes outside family A and no unresolved blocking threads.

Historical R-series workflows do not define current architecture authority.
