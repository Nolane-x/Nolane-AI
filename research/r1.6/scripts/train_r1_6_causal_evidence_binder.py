# R1.6 Effect-Conditioned Structured-Atom Binder training protocol
#
# Parent: Nolane-R1.6-NS2-PSRPlanner.pt
# Fit: train indices 56-65/family = 30 worlds
# Internal validation: train indices 66-68/family = 9 worlds
# Fresh: unopened
#
# A teacher-forced recurrent cache is built using the exact retained parent.
# Every row stores:
#   - parent full-policy logits;
#   - current structured atom embeddings + mask;
#   - contrastive public effect sketch for every dynamic action;
#   - action evidence counts;
#   - teacher action label.
#
# Trainable only:
#   causal_evidence_query
#   causal_evidence_scorer
#   causal_evidence_policy_scale
# Total: 295,938 parameters.
# Every other model parameter, including PSR/PSRPlanner, is frozen.
#
# Objective: CE(parent_logits + causal_evidence_bonus, teacher_action)
# plus tiny L2 on the binder network.
# Optimizer:
#   network lr=1.2e-3, weight_decay=2e-4
#   scalar scale lr=2.5e-2
# 80 epochs.
#
# A candidate can be selected only when internal-val CE improves and action
# accuracy is not below the parent baseline. Exact executable source is stored
# in the milestone ZIP/Library.
