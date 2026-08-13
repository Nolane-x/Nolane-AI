# R1.8 Verified Active Executive — Internal Training Acceptance

Date: 2026-08-13
Parent: ControlEffect `ec50d7240d0f3c4073fd849e62e9832a2bde6ab24ecad5cc4c59251dfb3a9f20`
Benchmark: FIGG-18 v1 (`train` only)

## Checkpoint
- `checkpoints/Nolane-R1.8-CCSM-ActiveExecutive.pt`
- SHA-256: `cb7159d1eb941f2cbae3c8f8fd6d4ddc4bd107384284a2444a4d1e2c5b404a40`
- effective parameters: **77,551,709**
- trainable executive parameters: **857,857**
- checkpoint bytes: **112,216,178**

## Locked protocol
- fit indices: `200..279` per family = 320 train worlds
- validation: `280..299` per family = 80 train worlds
- untouched closed-loop train gate reserved: `300..319` per family = 80 worlds
- seed `180818`
- max sequence steps 16
- 25 epochs, AdamW lr `1e-3`, weight decay `1e-4`, clip 1.0
- one optimizer update per complete cached episode
- only `r18_executive_*` parameters trainable
- checkpoint selection solely by lowest validation cross-entropy

## Runtime continuity
Long-lived multi-epoch Python processes stalled after 2-3 epochs despite a measured single epoch taking ~5-8 seconds. Training was therefore executed as process-isolated one-epoch resumes. A TDD regression proved that `2 epochs continuous` and `1 epoch -> snapshot exact executive weights + AdamW state + Torch RNG -> reconstruct -> epoch 2` produce byte-identical executive weights. Every resumed epoch atomically stored current weights, optimizer state and exact RNG before the next process.

## Validation
Initial validation:
- CE **1.5043096**
- accuracy **22.93%**

Best checkpoint: **epoch 6**
- CE **0.8108007283**
- accuracy **51.65%**

The run continued through all 25 preregistered epochs. Later epochs overfit; epoch 6 remained the lowest validation CE and was restored before final checkpoint save.

## Independent verification
The final checkpoint was reloaded from disk. Validation CE reproduced within `4.2e-9`; SHA and parameter count matched. Complete R1.7+R1.8 focused regression: **126/126 passed**.

## Claim boundary
This accepts the checkpoint only for the preregistered untouched train closed-loop gate. Teacher-forced CE/accuracy is not a closed-loop capability claim. FIGG-18 dev and fresh remain unopened.
