# Nolane R1.9 Frontier-Generalization — Complete Delivery

This milestone recovers the R1.7 Phase-C lineage, restores the real R1.8 parent checkpoint, and accepts the R1.9 neural rollout delta under locked internal/DEV/FRESH evaluation.

## Current accepted state

- parent: R1.8 ConditionalLaw, 76,619,419 effective parameters
- delta: R1.9 FrontierRollout, 1,594,754 parameters
- effective total: **78,214,173 parameters**
- internal two-step rollout MSE improvement: **38.8033%**
- DEV improvement: **39.5281%**
- FRESH improvement: **41.2256%**
- fresh consumed: **yes**
- post-fresh model/evaluator tuning: **forbidden and not performed**
- focused R1.8/R1.9 gate: **31/31 passed**

## Binary checkpoint boundary

The complete delivery contains eight real `.pt` checkpoints totaling 598,970,206 bytes. `WEIGHTS_MANIFEST_R1_9.json` binds each by exact size and SHA-256. The connected conversational GitHub channel cannot practically transfer 90–108MB binary blobs through model-mediated base64 arguments and exposes no LFS/release-asset upload action, so no fake weight placeholder is committed. `.gitattributes` and `scripts/publish_weights_lfs.sh` define the authenticated Git LFS publication path.

The COMPLETE ZIP and split recovery volumes preserve the actual weight bytes outside GitHub until a binary-capable authenticated git/LFS channel is used.

See `research/R1_9_REALITY_REPORT.md`, `research/R1_9_CURRENT_BEST.json`, `research/R1_9_PRE_FRESH_LOCK.json`, and `WEIGHTS_MANIFEST_R1_9.json`.
