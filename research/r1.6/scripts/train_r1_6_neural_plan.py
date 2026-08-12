# R1.6 Neural Plan Rollout training protocol
#
# Parent: Nolane-R1.6-NS2-CounterfactualWorld.pt
# Train: 30 tasks/family = 90 procedural worlds, 621 current states
# Future-action labels: 2,437 (up to horizon 6)
# Trainable planner parameters: 724,737
# Epochs: 18
# Fresh: unopened
#
# Objective:
# - cross entropy for each valid future teacher action in plan_logits[:, horizon_step]
# - current-action CE through the zero-init plan residual
# - small regularization on plan_policy_scale
#
# Training trajectory:
# - future plan accuracy: 20.23% -> 44.07%
# - current action accuracy: ~54.11% -> peak ~55.23%
# - tanh(plan_policy_scale) at epoch 18: ~0.01076
#
# Saved checkpoint:
# Nolane-R1.6-NS2-NeuralPlan.pt
# SHA-256: d12bdbd7dd4f2fff7933a4e8727f4d2ccf4d2f6f2b36a0a6c1a7d8ced5bbafba
# Effective candidate parameters: 70,268,531
