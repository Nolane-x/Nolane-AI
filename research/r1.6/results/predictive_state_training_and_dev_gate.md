# R1.6 Predictive State Representation — Training + Held-Out Dev Gate

Date: 2026-08-12 (Asia/Bangkok)

## Training protocol

Parent: `Nolane-R1.6-NS2-BoundedTransitionInternal.pt`

Train-only selection:

- fit: **10 worlds/family = 30 worlds**, 201 teacher states;
- internal validation: **3 worlds/family = 9 worlds**, 62 teacher states;
- all resource/rule actions supervised;
- causal opaque actuator transitions supervised only after the actuator has public action-memory evidence; terminal/done actions remain supervised from public state;
- targets: counterfactual public next-state sketch + progress + information + failure + done;
- trainable PSR parameters: **724,740**;
- parent trunk/policy/action-memory/world modules frozen;
- 80 epochs;
- fresh: unopened.

Internal validation at retained checkpoint:

- PSR state MSE: **0.002408**
- persistence MSE: **0.003695**
- improvement: ~**34.8%**
- failure accuracy: **93.68%**
- done accuracy: **100%**

Retained checkpoint:

- `Nolane-R1.6-NS2-PredictiveState.pt`
- SHA-256: `5306605801150c98461500d8e279e971536996d174645a070f1b3184596ab908`
- effective candidate parameters: **70,993,912**

## New held-out dev gate

Evaluation slice: **dev indices 18-23/family**, 18 worlds, 112 teacher states, 484 supervised known-action successors. This slice was not used by prior transition/MPC/policy gates.

Overall:

- PSR state MSE: **0.0029319**
- persistence MSE: **0.0044193**
- improvement: **33.66%**
- failure accuracy: **93.80%**
- done accuracy: **100%**

Family breakdown:

| Family | PSR MSE | Persistence MSE | Failure acc | Done acc |
|---|---:|---:|---:|---:|
| causal identification | 0.0014049 | **0.0013051** | 95.16% | 100% |
| delayed resource | **0.0017902** | 0.0041715 | 92.94% | 100% |
| compositional rule | **0.0075079** | 0.0086987 | 94.29% | 100% |

## Verdict

**PASS — PSR retained as a generalized world-model capability.**

Unlike recursive Stage-2 latent imagination, this model operates in a public, explicitly supervised state space and generalizes strongly on overall held-out state transition plus failure/done outcomes. Causal next-state sketch remains slightly better served by persistence and should use confidence/evidence gating in future planning.

The next gate is not more transition fitting. It is whether recursive PSR planning can convert this predictive capability into additional closed-loop task solutions on another untouched dev slice.

Fresh remains unopened.
