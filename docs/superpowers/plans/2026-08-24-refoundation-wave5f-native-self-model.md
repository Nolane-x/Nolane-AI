# Refoundation Epoch 0 — Wave 5F Native Self-model Plan

## Goal
Native-cutover `external.self_model` as the smallest next provable unit after hosted-green Wave 5E.

## Sequence
1. Add RED contracts for status/version, exact `SelfModel`/`SelfModelRegistry` identity, reverse-import absence, evidence-gated update semantics, initialization/state restoration, inventory provenance, scope isolation, and debt 39.
2. Prove hosted RED only fails on not-yet-cutover architecture/debt.
3. Move the accepted implementation into `nolane.external_core.self_model`, importing canonical Identity and Evidence owners.
4. Turn `cogcoder.organization.self_model` into an exact compatibility bridge.
5. Remove only the Self-model facade; add native implementation authority, local revision 1, and exact pinned inventory provenance.
6. Make prior cross-wave tests forward-compatible only where they freeze Self-model as a facade/version-0 component.
7. Deterministically regenerate native debt; require archive index no-drift.
8. Use a temporary branch-scoped, idempotent, fail-closed contents-write bootstrap only if required for multi-file authority/debt surgery; delete it before acceptance and enforce cleanup with a test.
9. Run complete exact-head Refoundation CI on Python 3.11 and 3.13 through zero-loss evidence, full organization/campaign/execution regressions, and frozen Neural R2.3 metadata.
10. Record exact head/run/artifact digests and mark the stacked PR Ready only after both runtimes are green. Never auto-merge.

## Target debt
- compatibility facade: 27
- legacy internal: 4
- historical only: 7
- frozen asset: 1
- total non-native: 39

## Following decision
After acceptance, re-evaluate Experience versus Skills. Experience is isolated but still uses canonical-digest shared debt; Skills requires extraction of `SkillScope` from mixed historical types, so it should not be native-marked until that schema ownership is resolved honestly.
