# Truth / Knowledge — External Core A

Status: **A1–A15 are accepted as the canonical External Core family-A Truth / Knowledge baseline. A15 Context-Qualified Truth v9 was merged to `main` as `461c68e4166e149cd605c4cd9b050da0cf2308ed`.**

This document is the compact current architecture authority. The byte-identical A1–A14 historical acceptance record that previously occupied this file is preserved at `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A1_A14_HISTORY.md`. A15's detailed production evidence is preserved at `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A15_ACCEPTANCE.md`.

## Canonical authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

Truth protocol modules are additive semantics beneath those authorities. Temporal, provenance, justification, undercutter, dependence, and context helpers must expose only their accepted `PARENT_COMPONENT_ID`; none may mint a sixth `COMPONENT_ID`.

All canonical Truth identity uses `nolane.core.canonical_digest.canonical_digest`.

## Accepted protocol progression

```text
global v1
    ↓
dependency-scope v2
    ↓
relation-aware-scope v3
    ↓
relation-aware-temporal v4
    ↓
provenance-lineage-temporal v5
    ↓
justification-provenance-lineage-temporal v6
    ↓
defeasible-justification-provenance-lineage-temporal v7
    ↓
dependence-defeasible-justification-provenance-lineage-temporal v8
    ↓
context-dependence-defeasible-justification-provenance-lineage-temporal v9
```

Every version is an exact protocol domain. Historical receipts, scopes, registries, and certificates remain historical exact modes; a v1–v8 object cannot silently masquerade as v9 and v9 cannot silently downgrade.

## A1–A14 accepted substrate

A15 inherits rather than replaces the accepted substrate:

- immutable, provenance-aware Evidence with anti-rebinding, revocation, polarity, channels, and tamper-evident restore;
- content-addressed Knowledge propositions with derivation DAGs and canonical set ordering;
- first-class `UNKNOWN`, `SUPPORTED`, `REFUTED`, and `CONTRADICTED` epistemic state plus explicit debt;
- dependency-local fixed points so unrelated state cannot stale a claim;
- canonical relation cardinality for exclusive, multi-valued, and unspecified relations;
- explicit deterministic temporal applicability with no implicit wall clock;
- append-only source-provenance lineage and controller-derived independence;
- OR-of-AND truth maintenance with explicit alternative justification lineages;
- exact-basis justification undercutters and defeasible inference status;
- append-only source-dependence metadata and conservative common-basis collapse;
- risk-sensitive live Assurance that never treats serialized certificate integrity as self-authenticating truth.

The complete A1–A14 acceptance history and exact historical run/merge identities remain preserved byte-for-byte in the acceptance-history document referenced above.

## Accepted A15 — Context-Qualified Truth v9

A15 closes the applicability gap left intentionally open by A14. Before v9, accepted truth could be temporal, provenance-bound, defeasible, and dependence-aware while still lacking a canonical way to say that a proposition or Evidence item is valid only under an explicit jurisdiction, environment, regime, policy mode, deployment class, or another caller-supplied context qualifier.

The central A15 law is:

> **Context determines applicability. Context never creates epistemic independence.**

A new context label cannot turn one controller into two controllers, one common basis into two independent bases, or one observation into independent corroboration.

### TruthContext

`TruthContext` is an immutable content-addressed value made from canonical unique qualifier key/value pairs. Qualifiers are deterministically ordered. Matching is requirement-based: every qualifier required by a binding must occur in the requested context with the exact value; additional caller context is allowed.

The empty `TruthContext` is the compatibility context.

### Evidence context binding

`evidence_context_truth.py` belongs to `external.evidence` and introduces append-only `EvidenceContextBindingRevision` history through `EvidenceContextBindingRegistry`.

Each revision exact-binds:

- Evidence ID;
- immutable `TruthEvidence.content_digest`;
- revision number;
- exact predecessor digest;
- canonical required qualifier set;
- canonical revision digest.

The registry enforces revision 1 with no predecessor, exact `+1` evolution, exact predecessor binding, no cross-ledger same-ID content rebinding, duplicate/gap/rollback rejection, and tamper-evident restore.

Unbound Evidence remains globally applicable for compatibility.

### Knowledge context binding

`knowledge_context_truth.py` belongs to `external.knowledge` and provides `ClaimContextBindingRevision` / `ClaimContextBindingRegistry` under the same append-only law.

A context revision binds the exact immutable `KnowledgeClaim.content_digest`; changing contextual applicability does not rewrite proposition identity or historical claim content.

Unbound Knowledge remains globally applicable for compatibility.

### Context-qualified Epistemic v9

`epistemic_context_truth.py` belongs to `external.epistemic`.

`ContextEpistemicJudge` preserves the exact accepted A14 dependence/provenance/defeasible/temporal audit scope, then re-evaluates claim and Evidence applicability under explicit `TruthContext`.

Important laws:

- a context-mismatched target remains in the audit scope and evaluates fail-closed rather than disappearing;
- a context-mismatched required parent or Evidence item invalidates only the derivation path that requires it;
- a dead context-invalid alternative cannot veto a separate live supported OR branch;
- contextual competitors that are not simultaneously applicable do not become artificial live contradictions;
- relation, temporal, provenance, justification, undercutter, and dependence semantics remain inherited from v3–v8 rather than reimplemented with weaker rules.

`ContextTruthScope` binds:

- exact accepted A14 audit dependence scope;
- exact `TruthContext`;
- target, lineage, fixed-point claims, Evidence, relations, audit sources, and decision sources;
- relevant source-provenance and source-dependence projections;
- relevant claim-context and Evidence-context projections;
- assessments, justification statuses, undercutter statuses, contradictions, debt, and mismatch IDs;
- canonical v9 digest.

Serialized v9 scope is not self-authenticating. Live validation must re-derive canonical state.

### Verification v9

`verification_context_truth.py` belongs to `external.verification` and defines a dedicated `ContextTruthVerificationReceipt` / `ContextTruthVerificationLedger` domain.

A receipt exact-binds:

- claim and verifier identity;
- channel and pass/fail result;
- exact v9 scope digest;
- exact `TruthContext.digest`;
- exact `TemporalContext.digest` and `as_of`;
- verification Evidence IDs;
- verifier source-provenance projection;
- verifier source-dependence projection;
- verification-Evidence context projection;
- canonical receipt digest.

Coverage validates live Evidence applicability in the exact requested context and rejects stale relevant context projections. Negative receipts remain retained.

Independence remains A14 independence: controller-root rules plus source-dependence/common-basis collapse. Context is deliberately absent from independence keys and dependence components. Two context labels applied to the same underlying controller or basis therefore still produce one epistemic independence component.

Relevant verification-Evidence context revision stales a receipt. An unrelated context revision outside the receipt/scope projection does not.

### Assurance v9

`assurance_context_truth.py` belongs to `external.assurance` and defines `ContextTruthClosureCertificate` plus `ContextTruthAssuranceGate`.

The gate recomputes live v9 state and preserves accepted risk thresholds:

- LOW/STANDARD → 1 independent verifier component + 1 channel;
- HIGH → 2 independent verifier components + 2 channels;
- CRITICAL → 3 independent verifier components + 3 channels.

Closure fails on, where applicable:

- target context mismatch;
- unsupported or conflicted live target;
- contributing-lineage conflict or unsupported state;
- critical epistemic debt or unresolved relation ambiguity;
- incomplete relevant source provenance/dependence;
- context-invalid, provenance-invalid, dependence-invalid, or negative verification;
- insufficient independent verification or channel diversity.

The certificate exact-binds v9 scope, v9 verification projection, TruthContext, TemporalContext, accepted receipt IDs, debt IDs, decision/reasons, and canonical digest. `validate_certificate()` recomputes canonical closure from live state.

## Compatibility and anti-laundering law

A15 is structurally additive:

- accepted `TruthEvidence` and `KnowledgeClaim` shapes are unchanged;
- v1–v8 protocol objects remain unchanged historical modes;
- empty `TruthContext` plus empty claim/Evidence context registries reproduces accepted A14/v8 epistemic semantics;
- all five A15 sidecars bind the existing five parents and expose no `COMPONENT_ID`;
- no canonical parent version is bumped solely because v9 sidecars exist;
- context cannot mint source/controller/channel/basis diversity;
- foreign-protocol, unexpected-field, digest-tampered, duplicate, revision-gap, predecessor, and same-ID content-rebinding restore attacks fail closed.

## A15 production acceptance proof

A15 is accepted from exact integrated candidate `08c461ae5b673a56d95f08936e6a958f7cc7660a`, built directly on then-current `main` `0cd7e955c53762ba593b4a0e56d90f7a29a2d807`.

The production chain is:

1. Verification RED head `8d17f9ae920a7bd0e0b4611a0553c7d0bdee15ed`, run `33397195863`, failed exactly because `verification_context_truth` did not exist while the prior A1–A14 compile remained green.
2. Verification v9, Assurance v9, authority hardening, empty-context A14 equivalence, context restore/tamper hardening, and CI v9 coverage were implemented additively. The pre-integration semantic candidate `8918f9df3136b9898ac49866145d3e547a743443` passed focused Truth Knowledge A run `33398916208` on Python 3.11 and 3.13.
3. To avoid concurrent non-A branch drift, the exact 18 intended A15 blobs were overlaid directly onto `main` `0cd7e955...`. This produced one-parent integrated candidate `08c461ae5b673a56d95f08936e6a958f7cc7660a` with tree `344c688476f7e97cb3a75b84c0f0c726f3dae769`; compare against that base was exactly one commit ahead, zero behind, and 18 intended files.
4. Fresh exact-head Truth Knowledge A run `33408419401` passed on Python 3.11 and 3.13, including A1–A15 v1–v9 compile, all **242 Truth/Knowledge tests**, and repository authority audit.
5. PR #303 synthetic merge `2703bbf55939c005ca1d3cd820d0364d91ba8e4a` exactly merged candidate `08c461ae...` into base `0cd7e955...`.
6. Full Refoundation Epoch 0 run `33408475216` passed on that exact synthetic merge on Python 3.11 and 3.13. Each matrix leg preserved 67/67 AI dossiers, repository audit `173 historical artifacts; 173 moved / 0 quarantined; 0 with reference debt; 1 non-native component records`, **685 Refoundation tests**, **242 Truth A tests**, zero-loss evidence generation/upload, **468 downstream organization/campaign/execution tests**, and Neural R2.3 PASS.
7. PR #303 was `mergeable=true`, contained exactly 18 intended A15 Family-A/CI/docs/test files, and had **0 reviews, 0 review threads, and 0 comments** blocking acceptance.
8. Final race guard confirmed `main` remained exact base `0cd7e955...`; PR #303 was merged with expected-head protection against exact candidate `08c461ae5b673a56d95f08936e6a958f7cc7660a`.
9. Production `main` advanced to verified merge commit `461c68e4166e149cd605c4cd9b050da0cf2308ed`, tree `344c688476f7e97cb3a75b84c0f0c726f3dae769`, whose exact parents are `0cd7e955c53762ba593b4a0e56d90f7a29a2d807` and `08c461ae5b673a56d95f08936e6a958f7cc7660a`.

A15 used Nolane World 0.12.0 as an external adversarial reasoning harness for context-reset, proxy/spec-gaming, source-independence, and exact verifier-evidence/context invariants. Nolane World is not imported as a canonical Nolane AI Truth authority; the transferred invariants are encoded in repository contracts.

This acceptance does not make v9 serialized runtime state self-authenticating. Every live scope, receipt, and closure certificate remains subject to canonical recomputation.

Canonical family-A status at this revision is therefore **A1–A15 accepted**.
