# Neural R2.1

The current evidence-backed neural candidate is **Neural R2.1a — Causal Evidence Router**. It is a tiny residual neural upgrade to the accepted R2.0i one-weight, designed to absorb part of the causal decision behavior that previously lived only in external runtime logic.

R2.1a adds **120,151 parameters** to the 78,779,253-parameter parent, for **78,899,404 effective parameters**. Deployment receives only public R2.0i neural tensors. The router is action-permutation equivariant and its score head is exactly zero-initialized, so an untrained instance is an exact parent-policy no-op.

Training uses set-valued action supervision before public evidence breaks action symmetry, parent-policy preservation on non-causal families, a causal-activation gate, and auxiliary functional-role supervision only where the role is publicly evidenced. Hidden role identity is not supplied at deployment.

A candidate delta was frozen before its first fresh evaluation. On the locked 80-episode FIGG-18 fresh slice (indices 900–919), neural-only solved count increased from **38/80 to 40/80**. Causal-prerequisite tasks improved from **2/20 to 4/20** while conditional-regime, regime-switch, and implicit-goal solved counts were unchanged. The exact frozen delta SHA-256 is `3bbd63c9cb20e180b78588e15a21e4132b41d80118c6ce229231967a91bfc9c4`.

The larger Recursive Latent Intelligence Core remains here as an experimental architecture. It adds 1,862,280 parameters and supports weight-shared iterative inference, but it is not designated the current best weight because no locked trained evaluation has yet shown it beating the smaller R2.1a candidate.

Claim boundary: the evidence supports a bounded neural-only improvement on the locked FIGG-18 slice. It does not establish AGI, frontier-model equivalence, universal reasoning, or equivalence to the full hybrid causal runtime.
