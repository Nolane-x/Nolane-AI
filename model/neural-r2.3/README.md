# Neural R2.3 — Ultra Recursive DAgger (79.86M physical)

Neural R2.3 is the first Nolane neural release in this lineage whose budget is defined by the **actual physical tensor parameter count**, not the historical `legacy_effective_parameters` compatibility number.

The accepted R2.1a parent contains **29,370,727 physical parameters**. R2.3 adds a **50,487,372-parameter** weight-shared recursive reasoner, producing **79,858,099 physical parameters total**, below the 80,000,000 physical ceiling.

The reasoner uses latent width 1344, 21 attention heads, SwiGLU recurrent refinement, per-action value/compatibility estimates and a repair gate. Deployment is fail-closed: the parent logits are returned unchanged unless the frozen neural gate exceeds `0.20539641380310059` and the recursive proposal selects a different action. The gate was retrained after freezing the reasoner with the precise target `parent wrong AND proposal correct`, not merely `parent wrong`.

Training combined expert trajectories with on-policy DAgger states so the model learns on states produced by learner behavior rather than only teacher trajectories. The final reasoner was calibrated on 4,160 held-out states after training on 11,539 cached expert+DAgger states.

Broad dev (indices 820–899, 320 episodes) improved **136→138**, with conditional regimes 47→47, regime switch 27→27, implicit goals 37→37 and causal prerequisites 25→27. The exact candidate was then frozen before fresh evaluation.

Two untouched fresh blocks were run without any post-fresh weight or threshold changes. Aggregate fresh result: **59/160→60/160**; conditional 19→19, regime switch 12→12, implicit goals 21→21, causal prerequisites 7→8. The gain is deliberately described as small: it is evidence of a bounded neural-only improvement, not AGI or frontier-model equivalence.

Frozen hashes and the physical tensor audit are authoritative in `evidence/` and `CURRENT_BEST.json`.
