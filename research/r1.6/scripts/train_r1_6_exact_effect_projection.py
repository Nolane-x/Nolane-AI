# R1.6 Exact Public Effect -> PSR training protocol
#
# Production implementation lives in cogcoder/neural_system2.py and is hashed
# in research/r1.6/patches/exact_public_effect_memory.md.
#
# Parent checkpoint:
#   Nolane-R1.6-NS2-PSRPlanner.pt
#
# Data isolation:
#   fit: train indices 30-39/family = 30 worlds
#   internal val: train indices 40-42/family = 9 worlds
#   fresh: unopened
#
# Each teacher step reconstructs the same recurrent dynamic action memory as the
# production agent. In parallel it maintains an exact action_effect_sketch
# [actions,128]. After previous_action is executed, the public structured
# numeric delta from previous observation -> current observation overwrites only
# that action's effect slot. Untried actions remain exactly zero.
#
# For resource/rule, all action counterfactuals are supervised. For causal
# identification, opaque actuator successors are supervised only when the
# actuator has already been probed (action count > 0), while done/terminal
# actions remain known from the public simulator surface.
#
# Frozen: every parameter in PSRPlanner except psr_effect_projection.weight.
# Trainable: 128x256 = 32,768 parameters.
# Optimizer: AdamW(lr=1.5e-3, weight_decay=2e-4), 100 epochs.
# Objective per action-count group:
#   10.0 * next-state sketch MSE
# + 0.8  * progress MSE
# + 0.45 * information BCE
# + 0.8  * failure BCE
# + 0.45 * done BCE
# + tiny projection L2 regularizer.
#
# Best internal checkpoint is selected only on train-internal validation loss.
# Closed-loop dev is not consulted during training/selection.
#
# Exact local executable source is preserved in the milestone ZIP/Library.
