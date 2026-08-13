# Nolane AI — R2.0i Active Causal Discovery

Nolane AI is an experimental compact cognitive system built around a small neural core plus explicit memory, verification and runtime control. The repository preserves rejected branches and separates **neural capability** from **hybrid runtime capability** rather than attributing scaffold gains to the weight itself.

## Current accepted deployment

The current accepted neural stack is **78,779,253 effective parameters**:

- R1.9 FrontierRollout parent: **78,214,173** effective parameters.
- R2.0e EvidenceEffect executive: **+565,080** parameters.
- R2.0i Active Causal Discovery: **+0 neural parameters**.

R2.0i is the first R2.0 candidate to pass the locked **TRAIN -> DEV -> FRESH** closed-loop admission sequence. Its prerequisite gain comes from a zero-parameter public active-experimentation controller around the neural stack. It is therefore a hybrid-system gain, not evidence that the neural weight alone learned that algorithm.

## Current deployment artifact: ONE weight

Use one checkpoint:

`Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`

- size: **59,773,663 bytes**
- SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`
- effective neural parameters: **78,779,253**
- contents: complete R1.9 standalone parent/frontier state + frozen R2.0e EvidenceEffectExecutive state + architecture/provenance metadata
- runtime binding: R2.0i controller SHA-256 `cc254838dd42e1081e888619f71276a3d1af1cf7ba0a55af7796ddbf39eec672`

`CURRENT_ONE_WEIGHT_R2_0I.json` is the canonical deployment manifest. `model/r2.0/cogcoder/r20i_standalone.py` loads the single neural weight. `model/r2.0/cogcoder/r20i_causal_discovery.py` supplies the zero-parameter public active-causal runtime required for the accepted hybrid behavior.

## Locked R2.0i evidence

### TRAIN — FIGG-18 indices 2000..2019

| Family | Frozen R2.0e depth1 | R2.0i hybrid |
|---|---:|---:|
| conditional regimes | 45% | 45% |
| regime switch | 30% | 30% |
| implicit goal regimes | 60% | 60% |
| causal prerequisites | 15% | **100%** |
| **Aggregate** | **37.5% (30/80)** | **58.75% (47/80)** |

Gain: **+21.25 percentage points**. Maximum family regression: **0**.

### DEV — indices 256..275

- baseline: **29/80 = 36.25%**
- R2.0i: **48/80 = 60.0%**
- gain: **+23.75 points**
- causal prerequisites: **5% -> 100%**
- maximum family regression: **0**

### FRESH — indices 512..531

The pre-fresh lock was committed before opening this split. R1.9's consumed fresh 0..7 region was not reused.

- baseline: **29/80 = 36.25%**
- R2.0i: **48/80 = 60.0%**
- gain: **+23.75 points**
- conditional: **50% -> 50%**
- regime switch: **25% -> 25%**
- implicit goal: **65% -> 65%**
- causal prerequisites: **5% -> 100%**
- maximum family regression: **0**

Fresh 512..531 is now **consumed**. No R2.0i tuning is allowed after that result.

The final one-weight deployment was then replayed on those already-consumed 80 fresh episodes purely as a packaging-reproduction check: **48/80 solved, 0 action/solve mismatches** versus the acceptance run.

## What the active-causal controller actually does

On prerequisite-like public environments, the controller does not know hidden action roles. Non-submit action descriptions remain opaque. It uses public experiments to infer:

1. which actuator changes auxiliary public state while the goal state is unchanged;
2. which actuator enables a prerequisite after sufficient accumulation;
3. which remaining opaque actuators control individual public state dimensions;
4. how to navigate the public state to the public target and submit.

A test proxy explicitly rejects private/non-contract attribute access. The runtime does not read hidden action kinds, hidden goal/resource/gate fields, transition internals, oracle plans or hidden answers.

For environments without this public prerequisite structure, R2.0i falls back exactly to the frozen R2.0e depth-1 policy.

## R2.0 negative research is retained

R2.0a-h were rejected rather than hidden. Among the key findings:

- deeper imagination alone did not improve closed-loop solve rate;
- full-trajectory supervision alone was insufficient;
- explicit public action/effect memory materially strengthened the shallow neural policy;
- depth-2 future simulation could regress action ranking;
- goal-directed value reduced regressions but did not meet admission gain;
- per-step and per-episode compute routing exposed complementary policies but did not transfer reliably to solve rate;
- causal prerequisites remained the dominant failure until active public experimentation was introduced.

See the `research/R2_0*` lock/result/rejection files for exact boundaries.

## Verification status

Current one-weight-oriented R1.9-frontier + R2.0e-i focused release suite:

```text
51 passed, 28 PyTorch warnings
```

A broader historical invocation additionally tried seven R1.9 rollout/training tests that require the old split `Nolane-R1.8-CCSM-ConditionalLaw.pt` binary. They stop with `FileNotFoundError` because this release intentionally carries one current deployment weight rather than restoring historical split checkpoint binaries. The repository does **not** claim that historical fixture-dependent suite is green.

## Benchmark integrity and frontier boundary

The project keeps train/DEV/FRESH locks, source/checkpoint SHA binding, one-time fresh consumption, negative-result retention, and explicit neural-vs-runtime ablations. `benchmarks/frontier100b/` also refuses a `hard_for_gt100b=true` claim unless an actual >100B reference model has been run under a locked protocol with a measured score and budget.

**R2.0i is not AGI and is not evidence of superiority to >100B models.** ARC-AGI-2, HLE/HLE-Verified, FrontierMath, Terminal-Bench and other external frontier suites still need actual official/verifier-backed runs before broad frontier claims are allowed.

## Key files

- `model/r2.0/cogcoder/r20e_executive.py` — frozen EvidenceEffect neural executive
- `model/r2.0/cogcoder/r20i_causal_discovery.py` — zero-parameter public active-causal runtime
- `model/r2.0/cogcoder/r20i_standalone.py` — one-file neural deployment loader/builder
- `research/R2_0I_REALITY_REPORT.md` — exact scientific claim boundary
- `research/R2_0_CURRENT_BEST.json` — current accepted state
- `research/R2_0I_PRE_FRESH_LOCK.json` — immutable fresh lock
- `research/r2.0/results/r2_0i_dev.json` and `r2_0i_fresh.json` — transfer evidence
- `CURRENT_ONE_WEIGHT_R2_0I.json` — canonical one-weight deployment manifest
- `benchmarks/frontier100b/` — external frontier comparison contract

## GitHub binary boundary

Source, loaders, tests, locks, results, manifests and CI live on `main`. The current conversational GitHub connector still does not expose a practical local-binary/LFS/release-asset upload path, so the raw ~59.8MB one-weight bytes are preserved in ChatGPT Library and the milestone download instead of being replaced by a fake pointer. The repository keeps exact SHA-256 provenance for that binary.

## License

Research code currently follows licenses embedded in imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
