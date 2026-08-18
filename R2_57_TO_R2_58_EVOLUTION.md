# R2.57 → R2.58 Evolution

R2.57 proved that a verified learned vocabulary can expose a useful latent progress variable and transfer it into downstream synthesis, but the external harness still chose the decisive experiment by fixing the target's endpoint-output inputs to 0 and 1.

R2.58 removes that hand-selected field pair. It adds a zero-parameter positional intervention search that enumerates legal reversible input rewrites, synthesizes the induced probe with the learned vocabulary, verifies it on separate probe contexts, and awards credit only when the probe causally changes the downstream result from failure to success under a matched frozen budget.

During implementation, R2.58 also exposed a separate confound: inherited synthesis ordering can depend on lexical field identities. R2.58 therefore canonicalizes the entire synthesis schema by input position before probe or downstream search, then maps the verified expression back to the external schema. Field-name renaming can no longer change intervention identity or candidate ordering inside this path.

The claim remains bounded. The intervention language is a finite pure-input anchor DSL; the anchor set and probe context families remain host-provided; the external family is still one numeric oracle. This is not arbitrary experiment invention, arbitrary latent-variable discovery, source induction, broad coding autonomy, or AGI.
