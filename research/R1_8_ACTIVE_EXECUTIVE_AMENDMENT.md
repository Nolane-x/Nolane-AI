# R1.8 Plan Amendment — Verified Active Executive

Date: 2026-08-13

## Evidence forcing the amendment
The original R1.8 design required a broad high-precision static reliability certificate before planning. Four variants were evaluated on disjoint FIGG-18 train-only ranges and rejected without opening dev/fresh:
- parameter-free model-memory agreement;
- linear confidence on full structured effects;
- linear confidence on control-sufficient effects;
- nonlinear 57,985-param runtime certificate.

Meanwhile the underlying representations are materially better: accepted ConditionalLaw improves held-out structured-effect MSE by 75.64%, and accepted ControlEffect improves held-out role-relative MSE by 69.44%. A non-learned one-step geometry/progress controller nevertheless solves only 7/64 new train worlds. The missing capability is therefore active recurrent decision-making, not another static score head.

## Revised control principle
R1.8 will use a **Verified Active Executive**:
`observe -> update evidence -> recurrently choose explore/exploit/submit action -> execute exactly one action -> verify public effect/progress -> update recurrent state -> repeat`.

The world model is a proposal representation, never an unchecked multi-step rollout. Every action is followed by real public feedback before the next decision. This preserves the original safety/recovery spirit while avoiding an unworkable static coverage prerequisite.

## Neural executive
Add a shared dynamic-action recurrent executive (~0.8-1.2M parameters, still <96M total):
- state inputs: public structured state sketch128, context fingerprint64, current progress, budget fraction, previous public feedback;
- action inputs: frozen ConditionalLaw hidden256, frozen ControlEffect64, evidence metadata3, per-action observed progress/count memory2;
- recurrent state: GRU256;
- action scorer shared across dynamic actions, preserving permutation equivariance.

The R1.7 parent, ConditionalLaw, ControlEffect, action encoder and all existing policies remain frozen during Phase-D executive training.

## Train-only protocol partition
To avoid all previously consumed FIGG-18 training ranges, executive work starts at index 200.
- fit: `200..279` per family (320 worlds)
- validation/checkpoint selection: `280..299` per family (80 worlds)
- untouched train closed-loop gate: `300..319` per family (80 worlds)
- seed: `180818`

Teacher trajectories are public-input / hidden-label only. Within each public context, teacher explores each legal non-submit action at least once when solvability permits, then follows the exact oracle. Context-specific exploration counts reset only for unseen contexts. The model never receives hidden laws/goals as inputs.

## Training
Train only `r18_executive_*` parameters with sequence cross-entropy through recurrent state. Checkpoint selection uses validation CE only; teacher accuracy is not a capability claim.

## Closed-loop train gate
After checkpoint selection, evaluate the untouched 300..319 range without oracle labels. Controls:
1. random controller (5 repeats);
2. same executive with recurrent state reset every step (`no_recurrence`);
3. full recurrent executive.

The executive may proceed to FIGG-18 dev only if:
- full recurrent solved rate is strictly above random mean;
- full recurrent solved count is strictly above `no_recurrence` by at least 5/80;
- full recurrent does not score below `no_recurrence` in any family;
- no private simulator field is consumed by the evaluator.

A passing train closed-loop gate authorizes a separately preregistered FIGG-18 dev gate with additional memory/world ablations. FIGG-18 fresh remains unopened until a later immutable pre-fresh lock.
