# A15 — Context-Qualified Truth v9

## Status

Design checkpoint for External Core family A. This document does not accept A15; acceptance requires RED→GREEN proof, exact-head CI, merge-state Refoundation proof, expected-head production merge, and a separate acceptance seal.

## Problem

A1–A14 make truth dependency-scoped, relation-aware, temporal, provenance-bound, multi-justified, defeasible, and source-dependence-aware. They still lack a canonical non-temporal applicability context.

The v7 fixed point discovers same-subject/same-relation competitors and filters them temporally, but it cannot distinguish propositions that are only applicable in different jurisdictions, environments, operating modes, populations, configurations, or other explicit conditions. A proposition that is true under one condition can therefore be treated as contradicting a proposition under another condition. Evidence can likewise be reused outside the context in which it actually bears on a claim.

This is a truth-maintenance defect, not a presentation concern: applicability must be resolved before contradiction/support closure is minted.

## Binding

A15 introduces the exact binding mode:

`context-dependence-defeasible-justification-provenance-lineage-temporal-v9`

Historical v1–v8 modes remain exact historical protocols and are not reinterpreted.

## Authority law

A15 adds sidecars only. It does not add a canonical authority.

- `evidence_context_truth.py` declares `PARENT_COMPONENT_ID = "external.evidence"`.
- `knowledge_context_truth.py` declares `PARENT_COMPONENT_ID = "external.knowledge"`.
- `epistemic_context_truth.py` declares `PARENT_COMPONENT_ID = "external.epistemic"`.
- `verification_context_truth.py` declares `PARENT_COMPONENT_ID = "external.verification"`.
- `assurance_context_truth.py` declares `PARENT_COMPONENT_ID = "external.assurance"`.

No A15 sidecar may define `COMPONENT_ID`.

## Canonical truth context

`TruthContext` is an explicit caller input containing canonical qualifier key/value pairs.

Rules:

1. Keys and values are explicit non-empty strings.
2. Keys are unique.
3. Canonical representation is lexicographically sorted by key then value.
4. Context digest is domain-separated and content-addressed.
5. Empty context is valid.
6. A required qualifier set applies iff every required key/value pair is present and equal in the caller context.
7. Extra caller qualifiers do not invalidate a binding.

The context is not inferred from mutable process state, source family, free-form text, or caller identity.

## Claim applicability binding

`ClaimContextBindingRevision` binds:

- exact `claim_id`;
- exact immutable `KnowledgeClaim.content_digest`;
- strict revision number;
- exact predecessor digest after revision 1;
- canonical required qualifiers.

`ClaimContextBindingRegistry` is append-only and enforces revision 1 then +1, predecessor integrity, claim/content non-rebinding, deterministic restore, and relevant-only projection.

A claim with no binding is a legacy global claim. Registry projection MUST encode that state explicitly as `global`, so adding a future binding stales scopes that previously depended on global applicability.

## Evidence applicability binding

`EvidenceContextBindingRevision` and `EvidenceContextBindingRegistry` mirror the claim rules while binding exact `TruthEvidence.evidence_id` and `TruthEvidence.content_digest`.

Unbound evidence is legacy global evidence.

Evidence whose required qualifiers do not match the caller truth context cannot contribute support/refutation in that context. If a target-reachable justification requires such evidence, the path becomes unknown/debt rather than silently dropping the evidence.

## Epistemic v9 semantics

A15 must apply context before final disposition.

### Target applicability

- Global target: applicable everywhere.
- Bound target with full qualifier match: applicable.
- Bound target with missing or conflicting qualifier: target disposition is `UNKNOWN`; closure is blocked and a context-applicability debt is emitted.

### Competitors

A same-key competitor participates in contradiction only if it is applicable in the same caller truth context.

Therefore:

- exclusive claims in disjoint contexts do not contradict;
- exclusive claims whose bindings both match the caller context do contradict under existing relation semantics;
- global claims continue to participate in every context.

Non-applicable competitors may remain represented in broader historical/audit state if necessary, but they MUST NOT influence the context-qualified final disposition.

### Justifications

A justification is an AND over its evidence and parents as before, plus context applicability of those reachable elements.

- Context-mismatched evidence makes that path unknown/debt.
- A live supported parent that is non-applicable makes that path unknown/debt.
- A parent that appears only on a dead/non-applicable alternative cannot veto another live context-valid branch.

A claim remains OR over alternative justifications. Context does not convert OR into confidence or independence credit.

### Undercutters

An undercutter is effective only when its own required evidence/parent lineage is context-applicable. A context-mismatched undercutter cannot defeat a justification in the current context.

## Scope and staleness

`ContextTruthScope` binds all v9 inputs needed to reproduce the decision, including:

- explicit truth-context digest/state;
- relevant claim-context projection;
- relevant evidence-context projection;
- v8 dependence/provenance/temporal/justification/undercutter state required by the context-qualified fixed point;
- context-qualified assessments/statuses/debts/contradictions.

Relevant context revisions stale scope/certificates. Unrelated context revisions do not.

## Verification v9

A15 uses dedicated v9 receipts/coverage/ledger. v8 receipts cannot masquerade as v9.

Verification retains A14 common-basis component collapse and all A11–A14 controller/origin exclusions, but receipts additionally bind the exact context-qualified scope and caller truth-context digest.

A verifier does not gain independence credit merely because it evaluates a different context. Context qualification is applicability, not independence.

## Assurance v9

A15 uses dedicated v9 closure certificates and gate. v8 certificates cannot masquerade as v9.

All A14 assurance thresholds and fail-closed dependence rules remain. Closure additionally requires:

- target applicable in the exact truth context;
- no live context-applicability debt on the supported lineage;
- exact live scope/context validation;
- context-qualified verification coverage.

The certificate is non-self-authenticating and must become stale on any relevant context-binding revision.

## Compatibility

When both context registries are empty and the caller uses `TruthContext.create()` with no qualifiers, v9 must reproduce the accepted v8 target disposition, source/dependence coverage, and closure behavior. A15 is additive and does not rewrite v1–v8 serialized modes.

## Required regressions

1. Disjoint-context exclusive competitors do not contradict.
2. Same-context exclusive competitors do contradict.
3. Legacy global claims/evidence remain globally applicable.
4. Missing target qualifier yields UNKNOWN + debt and blocks closure.
5. Context-mismatched evidence blocks its justification.
6. Context-mismatched live parent blocks its justification.
7. Dead/non-applicable alternative parent does not veto another live branch.
8. Context-mismatched undercutter cannot defeat a valid path.
9. Relevant claim/evidence context revision stales scope/certificate.
10. Unrelated context revisions preserve scope/certificate.
11. Registry restore rejects protocol, duplicate, revision-gap, predecessor, and entity-digest rebind attacks.
12. v8 receipt/certificate cannot masquerade as v9.
13. All sidecars preserve the five-authority law and define no `COMPONENT_ID`.
14. Empty context/no bindings reproduces v8 behavior.

## Acceptance gate

A15 is accepted only after:

1. focused RED evidence;
2. GREEN implementation and hardening;
3. fresh Python 3.11/3.13 Truth A exact-head run;
4. intended Family-A diff and clean review surface;
5. fresh synthetic full Refoundation merge-state run;
6. latest-main race guard;
7. expected-head production merge;
8. separate docs-only acceptance seal;
9. fresh seal Truth + Refoundation merge-state proof;
10. expected-head seal merge and post-merge canonical verification.
