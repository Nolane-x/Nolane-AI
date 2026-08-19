# Neural R2.1 — Recursive Latent Intelligence Core

Neural R2.1 is a compact residual successor to the accepted R2.0i neural stack. It adds one shared 256-dimensional recursive reasoning cell rather than stacking depth-specific layers. The same parameters can be reused for additional latent reasoning iterations at inference time.

The delta contains 1,862,280 parameters. Combined with the 78,779,253-parameter R2.0i parent, the candidate contains 80,641,533 effective parameters and remains below the locked 81M ceiling.

The core is action-permutation equivariant, uses continuous non-parametric iteration features instead of learned finite step embeddings, and emits anytime policy trajectories plus progress, uncertainty and ponder signals. Action/effect refinement heads and the stop/success residual heads are zero-initialized, so attaching an untrained core is a policy no-op over R2.0i.

Training is proof-weighted distillation: verified external/runtime trajectories may supervise the core; samples with zero proof weight contribute no policy authority. The loss trains final policy quality, teacher agreement, useful intermediate depths, non-regressing deeper reasoning, reasoning-depth prediction, effect refinement and calibration. Warmup trains only the small delta; joint mode can subsequently fine-tune the upstream neural stack with a lower learning rate.

This directory defines architecture, training, checkpoint and integration contracts. It does not claim that untrained source code is a stronger trained checkpoint; admission of a trained R2.1 weight requires held-out evidence against the accepted R2.0i parent.
