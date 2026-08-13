# Nolane AI — R1.9 Frontier-Generalization Research

Nolane AI is an experimental compact neural cognitive system developed with explicit external-memory/workspace and verifier boundaries. The repository preserves accepted and rejected research branches rather than presenting scaffold performance as neural capability.

## Current accepted lineage

The project has progressed beyond the original ~50M label:

- **48.3M self-grown core** — recurrent/sparse-expert foundation.
- **R1.2–R1.6** — executive control, semantic perception, predictive state and System-2 mechanisms.
- **R1.7 NCPM** — **75,387,546 effective parameters**; learned operator executor + functional program composition.
- **R1.8 CCSM** — **76,619,419 effective parameters**; +1,231,873 conditional-law parameters over R1.7.
- **R1.9 FrontierRollout** — **78,214,173 effective parameters**; +1,594,754 recurrent relational rollout parameters over frozen R1.8.

R1.9 deliberately grows by only ~2.08% over R1.8. The new module predicts a residual correction to the additive composition of frozen R1.8 one-step causal effects; its recurrent refinement cell is weight-shared rather than duplicated with reasoning depth.

## Latest locked evidence — FIGG-19

R1.9 was trained only on preregistered `train` worlds and then frozen. The same checkpoint was evaluated on disjoint DEV and finally an untouched FRESH split.

| Gate | R1.8 additive baseline MSE | R1.9 MSE | Relative improvement |
|---|---:|---:|---:|
| Internal held-out train worlds | 0.00402608 | 0.00246383 | **38.80%** |
| DEV | 0.00391145 | 0.00236533 | **39.53%** |
| FRESH | 0.00379843 | 0.00223250 | **41.23%** |

All four preregistered families improved on FRESH:

- causal prerequisites: **20.87%**
- conditional regimes: **47.26%**
- implicit-goal regimes: **46.89%**
- regime switch: **44.84%**

The FRESH split is now **consumed**. `research/R1_9_PRE_FRESH_LOCK.json` binds the checkpoint and evaluation settings, and no model/evaluator tuning is permitted after that fresh evaluation.

## Benchmark integrity

The project treats benchmark integrity as part of the research object:

- training collectors reject DEV/FRESH worlds;
- hidden/private answer fields are not model inputs;
- parent tensors are frozen and digest-checked;
- candidate and baseline are scored on identical rows;
- acceptance requires every family to improve, not only aggregate metrics;
- fresh checkpoints/splits are SHA-bound before opening;
- negative results and inherited failures are reported rather than hidden.

`benchmarks/frontier100b/` adds an external evaluation contract inspired by ARC-AGI-2, HLE/HLE-Verified, FrontierMath and Terminal-Bench. It explicitly refuses `hard_for_gt100b=true` unless a named >100B model has actually been evaluated with a finite score, recorded budget and locked protocol SHA.

**No >100B model has been run in R1.9 yet, so this repository does not claim that Nolane beats >100B systems.**

## Test status

The focused R1.8 + R1.9 research gate is green:

```text
31 passed, 11 warnings
```

A broad historical suite is **not** claimed clean. During the R1.9 audit, two inherited legacy `EffectProgressCritic` interface failures were observed in the recovered R1.7 lineage; they were not introduced by R1.9. Because fresh had already been consumed, model/evaluator code was not changed afterward merely to improve the test headline.

## Real weights and provenance

The complete R1.9 delivery contains **8 real PyTorch checkpoints** totaling **598,970,206 bytes**. Important current hashes:

- R1.7 OperatorExecutor: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
- R1.8 ConditionalLaw: `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`
- R1.9 FrontierRollout delta: `1b088c7837b76d37d3d1b288189f4a2ee9b378f069a398867ededef8c2a4d279`

`WEIGHTS_MANIFEST_R1_9.json` records exact size and SHA-256 for every included checkpoint.

The conversational GitHub channel can publish source/manifests but cannot practically stream the 90–108MB binary checkpoints through model-mediated base64, and it exposes no LFS/release-asset upload action. Therefore this repo does **not** contain fake weight placeholders. `.gitattributes` and `scripts/publish_weights_lfs.sh` define the authenticated Git LFS path for publishing the real binaries from the COMPLETE delivery.

## R1.9 files

- `model/r1.9/cogcoder/r19_frontier.py` — recurrent residual rollout head
- `model/r1.9/cogcoder/r19_rollout.py` — locked two-step counterfactual collector
- `model/r1.9/cogcoder/r19_training.py` — training/evaluation/checkpoint gate
- `model/r1.9/scripts/train_r19_frontier_rollout.py` — preregistered trainer
- `model/r1.9/tests/` — isolation, equivariance, parameter and provenance tests
- `benchmarks/frontier100b/` — external frontier comparison contract
- `research/R1_9_REALITY_REPORT.md` — exact claim boundary and results
- `research/R1_9_CURRENT_BEST.json` — current accepted lineage
- `research/R1_9_PRE_FRESH_LOCK.json` — immutable fresh lock
- `research/r1.9/results/` — DEV/FRESH evidence
- `WEIGHTS_MANIFEST_R1_9.json` — binary provenance

## Scientific boundary

R1.9 demonstrates a bounded gain in two-step conditional-causal rollout prediction with transfer to a fresh procedural split while adding only ~1.59M parameters. It does **not** prove AGI, broad language intelligence, long-horizon open-world planning, performance on ARC-AGI-2/HLE/FrontierMath/Terminal-Bench without actually running them, or superiority to frontier >100B models.

## License

Research code currently follows licenses embedded in imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
