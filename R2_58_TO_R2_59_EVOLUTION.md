# R2.58 → R2.59 Evolution

R2.58 made intervention selection autonomous, but its search architecture repeated overlapping probe synthesis for every intervention candidate. The frozen R2.58 authored gate counted **261,169** synthesis candidates across two full searches, and the pinned external transfer counted **136,969** for only 20 legal interventions.

R2.59 changes the search substrate rather than adding another task-specific rule. It preserves R2.58 positional canonicalization and causal downstream verification, but turns promoted R2.57 vocabulary expressions into a **resumable semantic index** shared by all intervention targets with the same free-position projection. Search advances in bounded fair slices, exact semantic targets reuse already-evaluated expressions, and downstream synthesis is cached by content-addressed seed digest.

R2.59 also removes the separate `anchor_values` input from its primary discovery API. Intervention anchors are derived deterministically from the public numeric constants already present in the downstream synthesis need. This does not invent a new constant language; it removes one redundant host-selected channel.

The frozen authored gate preserves 3/3 discovery, 12/12 probe validation, rename/permutation invariance and zero wrong-role false accepts while reducing synthesis candidates from R2.58's **261,169** to **10,943** (**23.866307×**). The hosted external gate is deliberately matched-distribution: it reuses the same pinned `ufunclab.linearstep` oracle to test whether the efficiency mechanism preserves R2.58 accuracy under a strict **15,000** global synthesis-candidate budget. It is not new external breadth evidence.
