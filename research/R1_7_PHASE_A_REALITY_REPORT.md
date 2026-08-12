# Nolane R1.7 Phase A Reality Report — Causal Law Slots

Date: 2026-08-12

## Verdict

**ACCEPTED as a bounded world-model capability; NOT YET accepted as a closed-loop policy capability.**

R1.7 Phase A adds eight content-addressed recurrent Causal Law Slots to the frozen R1.6 EffectProgress fresh-best parent. The law system learns from public state/action/effect transitions and predicts structured successor deltas for dynamic actions. It does not receive hidden simulator state as neural input.

## Parent

- R1.6 fresh-best SHA-256: `0a1688062f7640739847070a54ea079a28c10c010b286c5b640645214e912ace`
- effective parameters: 71,848,959

The R1.6 final delivery was restored byte-exact from Library volumes before R1.7 development. Its archive SHA matched `1ab75a90f56b88389fe2c0b4e03d15fd58310cd756986a32e1ffdccefd1e7101` and the documented parent regressions passed.

## FIGG-17 v1.1

R1.7 introduces a new procedural lineage independent of consumed R1.6 fresh tasks. An early v1 defect was discovered before optimizer training: arbitrary conditional-law goals could be unreachable. Training stopped before gradient step one. FIGG-17 v1.1 generates causal-law goals through witnessed valid trajectories and adds a 96-world oracle-solvability regression.

## Causal Law architecture

Eight 256D content-addressed recurrent slots receive public state sketches, dynamic action embeddings, and observed public successor deltas. Addressing/retrieval is shared across dynamic actions and permutation-equivariant. The R1.6 parent remains behavior-neutral before policy calibration.

Neutral candidate effective parameters: **73,642,371**. Trainable law-world parameters in this phase: **1,118,592**.

## Train-internal result

Last-observed-effect baseline vs learned law model:
- overall MSE: `0.00877359 -> 0.00415940` (**52.59% improvement**)
- causal_laws: **54.88% improvement**
- causal_switch: **49.97% improvement**

Checkpoint `Nolane-R1.7-NCPM-CausalLaws.pt`:
- SHA-256: `e6c99e5944b68c2fde7f89e7dec478b54e93f3a3250adfd806e1020b46239dbc`
- bytes: 96,541,771
- effective parameters: 73,642,371

## Held-out FIGG-17 dev result

Preregistered dev indices 64–79/family, 32 worlds total:
- overall MSE: `0.00820308 -> 0.00391423` (**52.28% improvement**)
- causal_laws: **53.65% improvement**
- causal_switch: **50.82% improvement**

## Negative result: policy usage

A separate 263,170-parameter law-policy residual calibration on a new train-only slice reduced validation CE slightly but did not improve combined causal teacher-action accuracy. The preregistered gate therefore selected `best_epoch=0`; no policy checkpoint was produced and no closed-loop FIGG-17 dev policy gate was opened.

The causal conclusion is narrow but useful: **the model learned dynamics, but has not yet learned to relate those dynamics to structured goal differences strongly enough to improve behavior.**

## Verification

- R1.7/R1.6 focused stack: **86/86 passed**
- parent/benchmark-integrity regressions: **33/33 passed**
- FIGG-17 fresh: **UNOPENED**

## Claim boundary

Phase A does not prove AGI or superiority to a 10B/100B model. It establishes a bounded world-model result: a ~73.6M Nolane candidate learns intervention-conditioned successor dynamics that beat a strong per-action last-effect baseline by ~52% on held-out FIGG-17 causal worlds.

The next justified component is the Goal-Difference Workspace from the approved R1.7 design, followed by a closed-loop completion/action-efficiency gate.
