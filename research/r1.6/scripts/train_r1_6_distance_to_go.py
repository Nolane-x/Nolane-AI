# R1.6 leakage-safe distance-to-go training protocol
#
# Parent: Nolane-R1.6-NS2-CounterfactualWorld.pt
# Train: 30 tasks/family = 90 procedural worlds, 621 teacher transitions
# Trainable: distance_head (640->1) + distance_policy_scale = 642 parameters
# Epochs: 80
#
# Targets deliberately avoid hidden shortest paths:
# - teacher-selected action: normalized remaining teacher-visible steps
# - any counterfactual immediate failure: distance=1
# - any counterfactual successful terminal action: distance=0
# - other alternative actions are not assigned a hidden-oracle distance target
#
# Policy: base_parent_logits - tanh(distance_policy_scale) * sigmoid(distance_head(world))
# The scale is initialized to zero, so parent behavior is preserved before training.
#
# Training result:
# - distance MAE: ~0.52 -> ~0.18-0.22
# - policy accuracy: ~54.1% -> peak ~54.8%
# - learned scale at epoch 80: ~0.129
# - checkpoint SHA-256: 0d61034e729816d87fd2143db4d3a522588971e78e706336c3055c826b7e8e64
# - fresh remained unopened
