# Nolane R2.6 — Invariant Program Induction — Delivery

Date: 2026-08-14
Status: **RESEARCH COMPLETE / PHASE-A REJECTED**
Official accepted system after this milestone: **R2.4 Long-Horizon Replanning**

## Executive result

R2.6 tested the hypothesis that exact-fit symbolic ARC programs can transfer better when new abstraction families are admitted only through a deterministic generalization firewall.

The development phase was positive but the preregistered held-out transfer gate was not.

- Frozen R2.5 baseline on the deterministic R2.6 split:
  - DEVELOPMENT: **55 / 801**
  - INTERNAL_HELDOUT: **21 / 199**
- Frozen R2.6 candidate:
  - DEVELOPMENT: **63 / 801**
  - INTERNAL_HELDOUT: **21 / 199**
- DEVELOPMENT gain: **+8 tasks** / **+14.55% relative**
- INTERNAL_HELDOUT gain: **0 tasks**
- Preregistered gate: **>=23 / 199**
- Actual gate: **21 / 199**
- Gate decision: **REJECTED**

R2.6 therefore does not replace R2.4 and must not be described as improved external ARC performance.

## Frozen candidate

Capability runtime commit:

`059ba04f134954880e19c1e6ec89d2ff5d0cdc1d`

Candidate lock:

`research/R2_6_CANDIDATE_LOCK.json`

Lock metadata amendment:

`research/R2_6_CANDIDATE_LOCK_AMENDMENT.json`

The amendment corrected stale/transcribed Git blob metadata only. The first verifier attempt stopped before held-out scoring and parsed no held-out task JSON. Runtime source, split, gate threshold, and budgets were unchanged.

## Protocol

ARC-AGI-2 revision:

`f3283f727488ad98fe575ea6a5ac981e4a188e49`

The 1,000 official training filenames were split without reading task contents:

`bucket = int(sha256(filename_utf8)[:8], 16) % 5`

- buckets 0–3: DEVELOPMENT = 801 tasks
- bucket 4: INTERNAL_HELDOUT = 199 tasks

Budget was fixed throughout candidate selection and gate execution:

- 2 attempts per test input
- 64 candidate programs per task

Held-out output was aggregate-only. No held-out task IDs, predictions, or task-level diagnostics were emitted.

## Generalization firewall

R2.6 introduced:

- deterministic filename-only development/heldout isolation;
- leave-one-demonstration-out re-inference;
- color-role canonicalization without raw-color semantic dependence;
- color-permutation consistency;
- horizontal-reflection consistency;
- square-grid 90-degree rotation consistency;
- evidence-bearing candidate ranking;
- strict exact-fit requirement before any candidate can be emitted.

The firewall alone did not improve DEVELOPMENT score: robustness-only re-ranking remained **55/801**. This negative result is recorded in `research/R2_6_DEV_RERANK.json`.

## New abstraction families

Only repeated DEVELOPMENT patterns were promoted, and every new family was introduced through RED→GREEN tests plus applicable firewall checks.

The successful development increments were:

1. structural extraction (`separator_map`, `separator_repack`, `frame_inner`): +4 tasks;
2. `unique_foreground_panel`: +1 task;
3. legend-driven color-pair swap: +1 task;
4. axis-generic border-marker motif repetition: +1 task;
5. graph-topological gate-to-marker path trim: +1 task.

Total: **+8 DEVELOPMENT tasks**.

The final candidate produced 84 robust candidates across 36 DEVELOPMENT tasks. New abstraction generation, rather than robustness-only ranking, was the source of the measured DEVELOPMENT gain.

## One-shot INTERNAL_HELDOUT gate

Gate workflow:

`.github/workflows/r26-heldout-gate.yml`

Scoring run:

- GitHub Actions run: `31768067019`
- job: `94667964225`
- aggregate artifact: `9207061852`
- aggregate artifact ZIP SHA256: `ac849c3532bef8a9f364b0d023836bb44373eb7b93b75760491d323406b7b095`

Result:

- cases: 199
- scored: 199
- solved: **21**
- solve rate: **10.5527638191%**
- errors: 0
- mean candidate programs: 0.4170854271
- mean attempts emitted: 0.1608040201
- gate minimum: 23
- gate pass: false

This exactly matches the frozen R2.5 baseline held-out solved count of 21.

## Scientific conclusion

The R2.6 hypothesis is rejected under its preregistered phase-A protocol. The added invariant abstractions improved the development partition but did not transfer to the internal held-out partition at all.

This is useful negative evidence: stronger task-internal invariance checks can prevent some brittle candidate behavior, but a small library of hand-designed abstraction families still does not provide broad distribution transfer. A future continuation must use a new protocol (R2.6b or later) rather than tuning against the consumed 199-task result.

## Accepted weight

R2.6 adds zero neural parameters and does not create a new accepted checkpoint. The milestone therefore carries forward the accepted neural binary used by R2.4:

`Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`

- effective neural parameters: 78,779,253
- SHA256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`

R2.4 remains the official accepted system.

## Claim boundary

R2.6 does **not** establish:

- ARC-AGI-2 public performance improvement;
- AGI capability;
- equivalence to or superiority over large language models;
- superiority over >100B-parameter systems.

The only supported R2.6 claims are the preregistered DEVELOPMENT and INTERNAL_HELDOUT measurements documented above.
