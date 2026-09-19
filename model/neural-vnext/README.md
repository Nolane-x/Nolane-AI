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

## Capability boundary

No result from this directory is an accepted Neural release until the locked neural-only gate is run after candidate freeze. Runtime, tool or full External Core gains cannot satisfy that gate.

See `CURRENT/NEURAL_CAPABILITY_SCOPE.md`.
