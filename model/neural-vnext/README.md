# Neural vNext — Multi-Depth Recursive Candidate

Status: **CANDIDATE ONLY — no capability promotion claim**

This is the first post-scope-correction Neural Core work. It deliberately changes neural computation/training rather than Evaluation, External Core, receipt, serialization or authority plumbing.

## Why this target

The accepted R2.3 reasoner is weight-shared and recurrent, but its accepted architecture metadata fixes `reasoning_steps_release = 1`. The model already contains recurrent depth features, a ponder head and per-depth trajectories, yet the accepted capability result barely uses that depth.

vNext therefore attacks a neural limitation directly:

- train the same neural tensors across multiple recurrent depths;
- supervise the ponder head to continue until a repair is stable;
- supervise delegation at every depth to open only for genuine parent-error repair;
- preserve the accepted parent distribution when the parent is already correct;
- choose a bounded learned depth at inference without adding trainable parameters.

The candidate remains at the R2.3 physical footprint because the adaptive wrapper introduces no trainable tensors.

## Phase 2: executable train → freeze → fresh gate

The candidate now has an executable path from verified neural teacher states to a frozen successor checkpoint:

1. `nvnext.pipeline.load_verified_training_cache(...)` accepts only proof-verified `expert` or `dagger` states.
2. Training cache provenance is fail-closed against every locked R2.3/vNext fresh index **1080–1159**.
3. `run_training_epoch(...)` drives the existing multi-depth objective over reproducible 2–4-step recurrent curricula.
4. `scripts/train_vnext.py` loads the exact accepted R2.3 one-weight checkpoint, verifies its SHA-256, runs warmup/joint training, and freezes a candidate delta.
5. Freeze authority binds the complete reasoner tensor state, adaptive-depth policy, exact predevelopment lock, parent checkpoint, physical parameter count, training-cache digest and bundle digest.
6. `scripts/evaluate_fresh_gate.py` refuses a changed/unfrozen bundle and evaluates only the preregistered 160 neural-only episodes at indices 1120–1159.
7. Promotion requires **at least +8 solved episodes** over the frozen R2.3 parent and **zero family regressions**. A passing gate is evidence for promotion; it does not rewrite accepted release metadata automatically.

The binary R2.3 one-weight checkpoint and verified training-state cache are intentionally not committed to Git. They are explicit inputs to the training CLI.

### Verified training-cache contract

The cache is a `torch.save` payload with:

- `format = "nolane-neural-vnext-verified-state-cache-v1"`;
- a non-empty `records` list;
- exact `source_index`, `family`, `source_kind`, `expert_action`, `proof_verified=true`, and positive finite `proof_weight`;
- unbatched tensors for every R2.3 reasoner input.

Records touching locked fresh indices are rejected before any optimizer step.

## Capability boundary

No result from this directory is an accepted Neural release until trained weights pass the locked neural-only gate after candidate freeze. Runtime, tool or full External Core gains cannot satisfy that gate.

See `CURRENT/NEURAL_CAPABILITY_SCOPE.md`.
