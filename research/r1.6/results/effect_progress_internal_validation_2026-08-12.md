# Effect-to-Progress Critic — train-only internal validation

Date: 2026-08-12 (Asia/Bangkok)

This candidate follows the preregistered protocol in `research/R1_6_EFFECT_PROGRESS_TRAINING_PROTOCOL.md`. R1.6 fresh remains unopened.

## Data / scope

- parent: recovered `CurrentBest.pt` = accepted PSRPlanner
- fit train indices: 82–91 per family
- internal validation train indices: 92–94 per family
- seed: 16120
- parent frozen
- trainable parameters: **98,818**, exclusively `effect_progress_critic.*`
- epochs: 40

## Internal validation

Frozen parent baseline:
- CE: `1.0327227`
- accuracy: `50.746%`
- causal identification: `35.714%`
- delayed resource: `67.857%`
- compositional rule: `45.455%`

Best candidate (epoch 40):
- CE: `0.4724257`
- accuracy: `83.582%`
- causal identification: `82.143%`
- delayed resource: `100.000%`
- compositional rule: `45.455%`
- learned critic scale (`tanh(raw)`): `-0.6687301`

The internal gate therefore passes. This is **not** yet a capability claim: prior R1.6 experiments established that teacher-forced accuracy can improve while closed-loop intelligence regresses.

## Candidate

- checkpoint: `checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt`
- SHA-256: `0a1688062f7640739847070a54ea079a28c10c010b286c5b640645214e912ace`
- effective parameters: `71,848,959`
- fresh opened: `false`

Next action is the frozen closed-loop gate on dev66–71 and dev72–77, with no tuning after results are observed.