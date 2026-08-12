# R1.6 Contrastive Effect -> PSR training protocol
#
# Parent: Nolane-R1.6-NS2-PSRPlanner.pt
# Fit: train indices 43-52/family = 30 worlds
# Internal validation: train indices 53-55/family = 9 worlds
# Fresh: unopened
# Trainable: psr_effect_projection.weight only (32,768 params)
# Epochs: 40 retained run (a prior 100-epoch attempt timed out at epoch 20
# before checkpoint creation and is not counted as a result).
#
# Recurrent public action-effect memory is reconstructed teacher-forced from
# public transitions. Before entering the PSR, raw action effects are converted
# with contrastive_action_effect_sketch(): one-shot evidence is preserved; once
# >=2 actions have evidence, the mean observed background dynamics are removed.
#
# Objective:
#   10.0 * counterfactual next-state sketch MSE
# + 0.8  * progress MSE
# + 0.45 * information BCE
# + 0.8  * failure BCE
# + 0.45 * done BCE
# + tiny projection L2.
#
# Every retained PSRPlanner weight is frozen. For causal opaque actuators,
# counterfactual successor supervision is used only after an actuator has public
# evidence; terminal/done actions remain supervised.
#
# The exact local executable source is preserved in the R1.6 milestone ZIP.
