# Goal/Design Truth-Maintenance Wave

## Objective

Close the remaining D-plane truth-maintenance authority gap without collapsing Requirements, Planning, Architecture, Integration, or Context ownership.

## Invariants

1. Assumptions are first-class, content-addressed authority dependencies, not free-form strings.
2. A truth-bound decision is admitted only against an exact assumption snapshot digest.
3. Truth policy is reversibility-sensitive and fail-closed for refuted assumptions.
4. Decision receipt v3 extends v2 identity; v1/v2 remain verifiable without retroactive truth binding.
5. Runtime invalidation is dependency-scoped: only decisions whose assumption closure intersects the changed truth closure become stale.
6. Transitive assumption dependencies are included in the bound snapshot and invalidation closure.
7. DecisionAuthorityIndex persists and restores v3 assumption bindings exactly and rejects tampering through receipt verification.
8. Truth changes mint causal authority invalidation events; unrelated truth changes do not mint false invalidations.
9. The organization facade exports truth-maintenance primitives without creating a second canonical writer.
10. Merge acceptance requires fresh exact-head Goal/Design CI on Python 3.11 and 3.12, plus a current-main integration check.

## TDD sequence

- [x] Implement standalone assumption truth substrate tests and implementation.
- [x] Add receipt-v3 RED tests.
- [x] Add runtime truth-bound admission/invalidation/persistence RED tests.
- [x] Correct one pre-existing test fixture that accidentally produced CONTESTED rather than REFUTED state.
- [ ] Add assumption refs to GoalSpec / DesignOption.
- [ ] Extend DecisionReceipt and authenticity verifier to v3.
- [ ] Bind assumption snapshot into admission input manifest and receipt identity.
- [ ] Wire AssumptionTruthMaintenance into GoalDesignRuntime admission.
- [ ] Index exact transitive assumption dependencies.
- [ ] Add truth-change invalidation with causal ledger authority events.
- [ ] Persist/restore v3 fields and assumption dependencies.
- [x] Export truth substrate from cogcoder.organization.goal_design.
- [ ] Run exact-head Goal/Design CI on Python 3.11 + 3.12.
- [ ] Integrate current main into feature branch and rerun exact-head CI if main drifted.
- [ ] Open/update PR only after green acceptance evidence.
