# R1.6 Bounded Transition — Held-Out Dev Gate

Date: 2026-08-12 (Asia/Bangkok)

## Training

- Parent: `Nolane-R1.6-NS2-CounterfactualWorld.pt`
- Train worlds: **90** (30/family)
- Teacher transitions: **621**
- Trainable parameters: **410,881** (`next_latent_head` direction + 641-param magnitude head)
- Train persistence MSE: **0.0041617**
- Final train transition MSE: **0.0038540**
- Mean predicted delta norm moved from ~0.0099 at initialization to ~0.823, close to the real train mean ~1.143
- Candidate: `Nolane-R1.6-NS2-BoundedTransition.pt`
- SHA-256: `7caf277c2efd7258f7040a15a7438639ffa60b7b1f27f264bd1865ec98f12054`
- Effective candidate parameters: **70,269,172** in the live experimental architecture
- Fresh: **not opened**

## Held-out dev one-step transition quality

| Family | N | Candidate MSE | Persistence MSE | Candidate cosine | Persistence cosine | Real delta norm | Pred delta norm |
|---|---:|---:|---:|---:|---:|---:|---:|
| causal identification | 54 | **0.0015298** | 0.0017665 | **0.998955** | 0.998769 | 0.815 | 0.792 |
| delayed resource | 51 | 0.0055038 | **0.0051606** | 0.996064 | **0.996306** | 1.315 | 0.943 |
| compositional rule | 21 | 0.0020538 | **0.0020242** | 0.998561 | **0.998594** | 0.942 | 0.524 |

Weighted overall:

- candidate MSE: **0.0032257**
- persistence MSE: **0.0031832**
- candidate is ~**1.33% worse** than persistence overall

For context, the old unconstrained transition was around **0.20-0.23 MSE** on these same family diagnostics with predicted delta norm ~11-12, so the bounded formulation removes the catastrophic off-manifold behavior by roughly two orders of magnitude.

## Verdict

**Trained checkpoint REJECTED as a capability transition** because the preregistered gate required beating persistence overall, and it did not.

**Bounded transition architecture RETAINED as a safety prior** because it eliminates the severe off-manifold transition failure: new/legacy-loaded models start close to persistence and cannot emit arbitrarily huge latent deltas. The next transition candidate must be tuned using train-internal validation rather than repeated dev sweeps, then receive one new held-out dev gate.

Fresh remains unopened.
