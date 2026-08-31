# Goal/Design Truth-Maintenance Wave

## Objective

Close the remaining D-plane assumption truth-maintenance authority gap without collapsing Requirements, Planning, Architecture, Integration, Context, or Family-A Truth/Knowledge ownership.

## Invariants

1. Assumptions are first-class, content-addressed Goal/Design dependencies, not free-form strings.
2. A truth-bound decision is admitted only against an exact transitive assumption snapshot digest.
3. Truth policy is reversibility-sensitive and fail-closed for known-refuted assumptions.
4. Decision receipt v3 extends v2 identity; v1/v2 remain verifiable without retroactive truth binding.
5. Runtime invalidation is dependency-scoped: only decisions whose bound assumption closure intersects the affected truth closure become stale.
6. Transitive assumption dependencies are included in both the bound snapshot and invalidation closure.
7. `DecisionAuthorityIndex` persists/restores v3 assumption bindings exactly and rejects tampering through receipt verification.
8. Truth changes mint causal authority events; unrelated truth changes do not mint false invalidations.
9. Robust/Pareto evaluation binds the Goal plus the **entire evaluated option set**, including alternative assumptions.
10. D assumption state is a Goal/Design-local decision projection. It declares no Family-A `COMPONENT_ID` and does not replace canonical `external.evidence`, `external.knowledge`, `external.epistemic`, `external.verification`, or `external.assurance`.
11. Historical v1/v2 identities remain stable through frozen compatibility bases; v3 is a monotonic public extension.
12. Merge acceptance requires fresh exact-head Goal/Design CI on Python 3.11 and 3.12 plus current-main merged-state verification.

## TDD / implementation sequence

- [x] Implement standalone assumption truth substrate tests and implementation.
- [x] Add receipt-v3 RED tests.
- [x] Add runtime truth-bound admission/invalidation/persistence RED tests.
- [x] Correct the test fixture that accidentally produced CONTESTED rather than REFUTED state.
- [x] Add `assumption_refs` to `GoalSpec` / `DesignOption` without reusing free-form legacy `assumptions` text.
- [x] Extend `DecisionReceipt` and the authenticity verifier to schema-aware v3.
- [x] Bind assumption snapshot state into the input manifest and final receipt identity.
- [x] Preserve exact v1/v2 identity semantics through `_goal_design_base.py` and `_goal_design_runtime_base.py`.
- [x] Wire `AssumptionTruthMaintenance` into `GoalDesignRuntime` admission.
- [x] Bind assumptions from Goal plus the complete evaluated option set.
- [x] Reject known-refuted assumptions before they can remain semantic inputs to robust/Pareto evaluation.
- [x] Index exact transitive assumption dependencies.
- [x] Add truth-change invalidation with causal `ASSUMPTION_CHANGE` + `INVALIDATION` authority events.
- [x] Persist/restore v3 fields and assumption dependency lookup.
- [x] Keep historical v2 decisions unbound to future truth changes.
- [x] Export D assumption primitives from `cogcoder.organization.goal_design` without introducing a second canonical Family-A writer.
- [x] Document the D ↔ Family-A authority boundary and future canonical evidence bridge.
- [x] Extend Goal/Design CI path coverage to v3 compatibility bases, truth documentation, and this closure plan.
- [ ] Integrate the latest `main` into the feature branch without overwriting concurrent specialist work.
- [ ] Run exact integrated-head Goal/Design CI on Python 3.11 + 3.12.
- [ ] Open the PR and require synthetic merged-state acceptance before merge.

## Executed evidence

### Initial runtime RED

Run `33356135114` on test-only head `90212e890b07aa70a84264c393b89307ecffc741` demonstrated missing v3/runtime wiring. Python 3.12 reached **74 passed / 13 failed**; failures were concentrated on the new `assumption_refs`, v3 receipt fields, runtime `truth` dependency, persistence, and invalidation APIs.

### Complete evaluated-option snapshot RED

Run `33361737349` on head `8214aec472ac5dbea28856940c63fb91fc18c8f9` reached **88 passed / 1 failed** on both Python versions. The sole failure proved that receipt refs already listed Goal + selected + alternative assumptions while the truth snapshot digest still bound only Goal + selected assumptions.

### Option-set binding GREEN

Run `33367779379` on head `b143554857f235d05db3d85cd2ff751f7e4063e5` completed:

- Python 3.11: **89 passed**
- Python 3.12: **89 passed**

### Refuted-alternative adversarial RED

Run `33367972341` on head `5478735aca081c20ab310321ab99f35dce58e44c` reached **89 passed / 1 failed** on both Python versions. The only failure was `DID NOT RAISE CoherenceError` when an alternative option used a known-refuted assumption, proving the evaluated-option policy gap.

The production fix applies the same reversibility-sensitive blocker policy to the complete evaluated assumption set: REFUTED always blocks; unsettled state remains class-sensitive.

## Remaining acceptance gate

Do not claim this wave merged or complete until the branch contains the current `main`, the exact integrated head passes Goal/Design CI on Python 3.11 and 3.12, PR merged-state verification is clean, and the actual merge SHA is verified on `main`.
