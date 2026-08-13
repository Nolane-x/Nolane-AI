# R1.7 Neural Operator Executor — ACCEPTED

Date: 2026-08-13
Benchmark: FIGG-17 v1.1 train-only single-step composition transitions
Parent world stack: accepted Goal-Difference / Causal Laws

The preregistered continuous 80-epoch protocol completed using resume-safe executor-only checkpoints. No optimizer/data/seed/objective change was made after metrics were observed. The selected executor state is epoch 18, the earliest/best state satisfying the strict transition gate.

## Protocol

- fit worlds: `composition_holdout` train indices 282..481 (200 worlds / 1,000 public one-step transitions)
- internal validation: indices 482..521 (40 worlds / 200 transitions)
- seed: 170917
- optimizer: AdamW
- lr: 0.002
- weight decay: 0.0001
- epochs: 80
- batch size: 128
- trainable scope: exactly `program_executor_*`
- parent/action encoder/world/policy weights frozen

## Held-out transition result

- exact full-vector accuracy: **199/200 = 99.5%**
- per-element accuracy: **796/800 = 99.5%**
- `rotate vector one cell left`: **100%**
- `reverse vector order`: **100%**
- `double each value modulo seven`: **100%**
- `swap adjacent pairs`: **100%**
- `add one modulo seven to each value`: **97.5%**

This passes the preregistered thresholds: exact >=98%, element >=99.5%, every operator >=95%.

## Checkpoint

- file: `checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt`
- SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
- bytes: 103,545,139
- effective candidate parameters: **75,387,546**
- hard ceiling: 96,000,000

## Independent verification

- re-evaluation on all 200 held-out transitions reproduced the metrics above
- focused R1.7 stack after acceptance: **77/77 tests passed**
- FIGG-17 dev/fresh remain unopened

## Persistent recovery

Incremental recovery ZIP was integrity-tested with `unzip -t` and persisted to ChatGPT Library:

`/Nolane/R1.7-Recovery/Nolane-R1.7-INCREMENTAL-OperatorExecutor-ACCEPTED-2026-08-13.zip`

Verified ZIP SHA-256 at persistence time:
`c02ae226df7ab9a9a725e9b3db1b6779699350dcde0d5224449e0fe2728dc539`

The executor gate proves reusable learned single-step public operator dynamics. It is not yet program-induction capability. The next preregistered step is Functional Program Search over public demonstrations with the accepted executor frozen.
