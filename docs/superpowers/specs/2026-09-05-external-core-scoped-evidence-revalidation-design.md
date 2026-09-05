# External Core Scoped Evidence Revalidation Design

## Context

External Core integration revalidation currently proves that a required `(component_id, evidence_kind)` pair has a clean `EvidenceRecord`, but the binding does not prove that the evidence was produced for the exact component version transition, exact revalidation plan, exact impact closure, or exact authority-graph state being assessed. This leaves a structural replay/cross-transition laundering gap: clean evidence from an earlier or different transition can be relabeled for a later plan when the component and evidence kind happen to match.

This change closes that gap without creating a global External Core version or a new authority family.

## Governing law

> Evidence may prove only the exact subject and context it was produced against; compatibility evidence must never be transferable merely because labels match.

## Component-local version impact

Only two canonical components change accepted semantics:

- `external.evidence`: `0.0.1 -> 0.0.2`
- `external.integration`: `0.0.2 -> 0.0.3`

No platform/global External Core version is introduced. No unrelated component revision is advanced.

## Authority boundaries

This feature is structural and read-only with respect to authority. It does not create family H, a central governor, a global orchestrator, invocation authority, verification authority, Assurance authority, promotion authority, deployment authority, repair authority, automatic migration authority, or runtime registration authority.

`external.evidence` owns content-addressed evidence identity and exact subject/context binding. `external.integration` owns compatibility/revalidation structure. Existing Verification and Assurance authorities remain external canonical owners of semantic verification/Assurance decisions.

## Evidence v2: scoped evidence

Legacy `EvidenceRecord` remains supported unchanged for existing consumers. A separate strict protocol is added for exact-context consumers.

### `ScopedEvidenceRecord`

Protocol: `scoped-evidence-v2`

Immutable fields:

- `evidence_id`: explicit stable evidence identity supplied by the producer
- `subject_id`: exact semantic subject being evaluated
- `subject_version`: exact subject version
- `subject_digest`: content digest of the exact subject state
- `scope_digest`: digest of the exact evaluation/revalidation context
- `verifier_agent_id`: external verifier identity
- `observed_epoch`: non-negative observation epoch
- `passed`: exact boolean; integer/string truthiness coercion is forbidden
- `false_accepts`: non-negative integer, booleans forbidden
- `regressions`: non-negative integer, booleans forbidden
- `evidence_refs`: non-empty canonical tuple of explicit evidence/provenance references
- `limitations`: canonical tuple of explicit limitations; may be empty
- `digest`: content digest over the full semantic payload

Creation and restore are strict. Restore rejects unknown/missing fields, non-string identity smuggling, boolean-as-integer, non-canonical list/set ordering, digest substitution, future/negative epochs supplied to consumers when a freshness fence is imposed, and direct-constructor forgery when consumed through `validate_integrity()`.

`ScopedEvidenceRecord` does not itself mean Truth, Verification, Assurance, authorization, promotion, successful execution, or release readiness.

## Integration scoped revalidation v2

Legacy integration revalidation v1 remains available for historical/backward-compatible state. The new exact-context path uses separate v2 protocols.

### `RevalidationScope`

Protocol: `integration-revalidation-scope-v2`

Content-addressed binding of:

- `delta_id`
- evolved `component_id`
- exact `old_manifest_digest`
- exact `new_manifest_digest`
- exact `old_component_version`
- exact `new_component_version`
- `impact_closure_id`
- `authority_graph_digest`
- `plan_id`

Creation requires a canonical `ComponentEvolutionDelta`, canonical `IntegrationImpactClosure`, and canonical `RevalidationPlan`, and recomputes all derived values. It rejects identity/version rebinding, plan/delta mismatch, closure mismatch, graph-digest mismatch, and direct-constructor forgery.

### `RevalidationChallenge`

Protocol: `integration-revalidation-challenge-v2`

One immutable challenge is derived for each `(component_id, evidence_kind)` requirement in a canonical plan. It binds:

- exact `scope_id`
- exact `plan_id`
- exact requirement id
- component id
- evidence kind
- basis codes
- target component version
- challenge id

For the evolved component, target version is the new manifest version. For impacted downstream components, target version is obtained from the exact authority graph manifest population used by the impact closure.

Challenges are deterministic and content-addressed; callers cannot substitute arbitrary challenge metadata.

### `ScopedRevalidationEvidenceBinding`

Protocol: `integration-revalidation-evidence-binding-v2`

A binding contains one canonical `RevalidationChallenge` and one canonical `ScopedEvidenceRecord`.

Admission requires exact equality of:

- evidence `subject_id` == challenge component id
- evidence `subject_version` == challenge target component version
- evidence `scope_digest` == challenge scope id
- evidence `subject_digest` == deterministic challenge subject digest derived from `(scope_id, challenge_id, component_id, target_version, evidence_kind, basis_codes)`

The component cannot self-certify: verifier identity equal to the subject component id is rejected.

### `ScopedRevalidationAssessment`

Protocol: `integration-revalidation-assessment-v2`

`assess_scoped_revalidation()` validates scope/plan/challenges/bindings before use.

Categorical outcomes remain:

- `CURRENT`: every exact challenge has exactly one clean, scope-bound evidence binding
- `REVALIDATION_REQUIRED`: required exact challenges remain missing
- `BLOCKED`: forged, duplicate, unexpected, stale, dirty, cross-scope, cross-version, or mismatched evidence is present
- `UNKNOWN`: reserved for explicit unknown state and never synthesized into CURRENT

A v1 `EvidenceRecord` cannot satisfy a v2 scoped challenge.

### `RevalidationCompletionReceipt`

Protocol: `integration-revalidation-completion-v2`

An immutable receipt can be created only from a canonical v2 assessment whose disposition is `CURRENT`. It binds:

- exact `scope_id`
- exact `plan_id`
- exact assessment id
- exact challenge ids
- exact scoped evidence binding ids
- completion receipt id

The receipt is descriptive proof that the structural revalidation requirements of that exact transition were satisfied. It is not Verification, Assurance, authorization, promotion, deployment approval, execution success, or release readiness.

## Replay and laundering defenses

The adversarial acceptance matrix must reject:

1. evidence from an older subject version reused for a new version;
2. evidence from one delta reused for another delta;
3. evidence from one plan reused for another plan;
4. evidence from the same plan but a different authority-graph digest;
5. old/new manifest substitution while retaining evidence;
6. challenge substitution or forged challenge id;
7. direct-constructor forged scope/challenge/binding/assessment/completion objects;
8. duplicate evidence for one challenge;
9. one binding reused to satisfy a different challenge;
10. self-verification;
11. non-string identity/type smuggling;
12. boolean-as-integer/boolean-as-passed coercion;
13. stale observation under an explicit minimum epoch fence;
14. clean evidence with the wrong subject digest or scope digest;
15. forged completion receipt;
16. v1 evidence presented to the v2 path.

## Public API

Safe structural/read-only v2 types and pure builders/assessors may be exported from `nolane.external_core`. No control-plane method names (`authorize`, `execute`, `promote`, `deploy`, `repair`, `assure`, `verify`, `register_runtime`, `auto_migrate`) are added.

## Version discipline and repository enforcement

The existing machine-enforced component-local version discipline remains authoritative. This change must advance exactly `external.evidence` and `external.integration` by one revision each. Version-only edits must remain insufficient; semantic source changes plus exact revision-map movement are required.

## CI acceptance

Acceptance requires on Python 3.11 and 3.13:

- External Core contracts including new scoped-evidence/revalidation tests;
- component-local version discipline with `0 finding(s)`;
- canonical component-version projection;
- canonical External Core coherence audit with `0 finding(s)`;
- prior G/Assurance regressions;
- Refoundation Epoch 0 substantive gates on the exact PR merge tree;
- review/thread scan before Ready/merge.

Historical frozen release-boundary witnesses are not refrozen merely to manufacture green CI.