# R1.8 Verified Active Executive — Train-Internal Protocol

Date: 2026-08-13
Parent world representation: accepted ControlEffect `ec50d7240d0f3c4073fd849e62e9832a2bde6ab24ecad5cc4c59251dfb3a9f20`.
Benchmark: FIGG-18 v1. No FIGG-18 dev/fresh task may be instantiated.

## Data partitions
- fit: train indices `200..279` inclusive per family = 320 worlds
- validation/checkpoint selection: `280..299` inclusive per family = 80 worlds
- untouched train closed-loop gate reserved: `300..319` inclusive per family = 80 worlds
- seed: `180818`

## Teacher trajectory
All model inputs are public-derived. Hidden simulator state may choose only the teacher label.

Within each public context:
1. if any legal non-submit action has not yet been explored in that context, choose the least-used safe action whose resulting state preserves an oracle continuation;
2. otherwise follow the exact oracle next action.

Context-specific exploration counts and per-action progress memories persist when a previously seen context returns. Evidence memory is also context-indexed. After every action, the next training state uses the **actual public** progress/effect/information/failure feedback.

Per-step frozen inputs:
- structured public state sketch 128D;
- key-name-agnostic public context fingerprint 64D;
- public progress scalar;
- public budget fraction relative to the episode's initial public budget;
- previous public feedback `[progress_delta, information_gain, failed]`;
- frozen ConditionalLaw hidden 256D/action;
- frozen accepted ControlEffect 64D/action;
- evidence metadata 3D/action;
- context-specific per-action progress memory `[last_progress_delta, normalized_count]`.

## Trainable scope
Exactly `r18_executive_*` parameters: **857,857 parameters**. R1.7 parent, ConditionalLaw, ControlEffect, action encoder, evidence memory, legacy policies and rejected certificate heads remain frozen.

## Optimization
- sequence cross-entropy through recurrent executive state;
- AdamW lr `1e-3`;
- weight decay `1e-4`;
- gradient clipping `1.0`;
- 25 epochs;
- one optimizer update per complete cached episode;
- checkpoint selected solely by **lowest validation CE** on indices 280..299.

Teacher-forced CE/accuracy is not a capability claim.

## Untouched train closed-loop gate
After the best-validation checkpoint is frozen, evaluate indices 300..319 per family with no oracle labels exposed to the policy. Controls:
1. random controller, 5 repeats;
2. same executive with recurrent state reset every step (`no_recurrence`);
3. full recurrent executive.

Acceptance to FIGG-18 dev requires:
- full recurrent solved count strictly above random mean;
- full recurrent solved count >= no_recurrence + 5 out of 80;
- full recurrent solved count not below no_recurrence in any family;
- evaluator/controller consumes public observation/feedback only.

FIGG-18 fresh remains unopened regardless of this gate.
