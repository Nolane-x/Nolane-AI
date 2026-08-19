# Neural R2.1

The current evidence-backed neural candidate is **Neural R2.1a — Causal Evidence Router**. It is a tiny residual neural upgrade to the accepted R2.0i one-weight, designed to absorb part of the causal decision behavior that previously lived only in external runtime logic.

## Parameter accounting

R2.1a adds **120,151 trainable parameters**. The preceding release line historically tracked a compatibility quantity called **effective parameters**: 78,779,253 for the parent and **78,899,404** after adding R2.1a. That historical quantity is retained in manifests so old release checks remain reproducible, but it is **not the physical unique tensor parameter count** of the serialized one-weight.

A post-release audit loaded the exact frozen one-weight (`sha256:4f0b366e2401127e50b7fdbca651601b0a4b972004812c9f32043b82f0e3091b`) through the canonical loader and independently counted every serialized tensor. Both methods give **29,370,727 physical loaded parameters**: NeuralSystem2 27,090,742 + FrontierRollout 1,594,754 + EvidenceEffect 565,080 + CausalEvidenceRouter 120,151. The frozen artifact filename still contains `78.9M` only for provenance compatibility; that token denotes the legacy-effective accounting, not a physical tensor count. Full evidence is in `evidence/R2_1A_PARAMETER_ACCOUNTING_AUDIT.json`.

Deployment receives only public R2.0i neural tensors. The router is action-permutation equivariant and its score head is exactly zero-initialized, so an untrained instance is an exact parent-policy no-op.

Training uses set-valued action supervision before public evidence breaks action symmetry, parent-policy preservation on non-causal families, a causal-activation gate, and auxiliary functional-role supervision only where the role is publicly evidenced. Hidden role identity is not supplied at deployment.

A candidate delta was frozen before its first fresh evaluation. On the locked 80-episode FIGG-18 fresh slice (indices 900–919), neural-only solved count increased from **38/80 to 40/80**. Causal-prerequisite tasks improved from **2/20 to 4/20** while conditional-regime, regime-switch, and implicit-goal solved counts were unchanged. The exact frozen delta SHA-256 is `3bbd63c9cb20e180b78588e15a21e4132b41d80118c6ce229231967a91bfc9c4`. The accounting audit does not alter these weights or reuse the fresh holdout for tuning.

The larger Recursive Latent Intelligence Core remains here as an experimental architecture. It adds 1,862,280 parameters under the existing legacy-effective budget projection and supports weight-shared iterative inference, but it is not designated the current best weight because no locked trained evaluation has yet shown it beating the smaller R2.1a candidate.

Claim boundary: the evidence supports a bounded neural-only improvement on the locked FIGG-18 slice. It does not establish AGI, frontier-model equivalence, universal reasoning, or equivalence to the full hybrid causal runtime.
