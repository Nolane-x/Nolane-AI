# Nolane R1.6 Neural System-2 — Complete Delivery

Date: 2026-08-12 (Asia/Bangkok)

R1.6 is closed. The fresh set is consumed and must not be reused as an untouched test.

## Complete ZIP

`Nolane-R1.6-Neural-System2-COMPLETE-DELIVERY-2026-08-12.zip`

- exact bytes: `3,788,846,806`
- SHA-256: `1ab75a90f56b88389fe2c0b4e03d15fd58310cd756986a32e1ffdccefd1e7101`
- `unzip -t`: **No errors detected in compressed data**
- contains the full current R1.6 project tree excluding only Python/pytest caches: source, tests, scripts, results/traces, reports, preregistration/lock artifacts, negative experiments, and **65 checkpoint files/weights**.

## Library persistence

Because one Library file is size-limited, the verified ZIP was split byte-for-byte into **21 ordered 180-MiB-class volumes** under:

`/Nolane/R1.6-Final/`

- parts `Nolane-R1.6-COMPLETE.part-00` through `part-20`
- parts 00–19: 188,743,680 bytes each
- part 20: 13,973,206 bytes
- total: 3,788,846,806 bytes
- `FINAL_VOLUMES_MANIFEST.json` records SHA-256 of every part and the original ZIP
- manifest SHA-256: `0fc35441a462d3d97bbc7863a8d67757c75868fb976c85b6f74876cda039e1ac`

Restore:

```bash
cat Nolane-R1.6-COMPLETE.part-* > Nolane-R1.6-Neural-System2-COMPLETE-DELIVERY-2026-08-12.zip
sha256sum Nolane-R1.6-Neural-System2-COMPLETE-DELIVERY-2026-08-12.zip
```

The restored SHA MUST equal `1ab75a90f56b88389fe2c0b4e03d15fd58310cd756986a32e1ffdccefd1e7101` before use.

## Locked fresh result summary

- PSRPlanner: 15/60
- EffectProgress: **28/60** (strongest locked checkpoint on consumed fresh)
- pre-fresh CurrentBest / RuleProgramBroad: 23/60
- oracle: 60/60
- random 10-repeat mean: 1.8/60

The cleanest paired generalization gain is PSRPlanner → EffectProgress: **13 gained tasks, 0 lost tasks**.

## Verification status

- immutable pre-fresh source/checkpoint hashes: PASS
- R1.6 + evaluator focused tests: 63/63 PASS
- R1.1/R1.2 + benchmark integrity regressions: 33/33 PASS
- historical full suite: incomplete/time-capped; two deterministic obsolete EffectProgress API contract tests fail because two historical same-name class definitions coexist. This is frozen as an R1.6 source-contract debt rather than fixed after fresh.

## Next-line rule

Any research informed by R1.6 fresh failures must be R1.7+ and use a new untouched benchmark version/split. The recommended research parent is the already-locked EffectProgress checkpoint (`0a168806...`), but R1.6 fresh can no longer serve as a clean test for descendants.