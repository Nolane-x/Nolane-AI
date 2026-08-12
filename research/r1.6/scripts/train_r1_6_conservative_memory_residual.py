# Exact trainer source is preserved in the R1.6 milestone workspace and ZIP. This GitHub mirror records the algorithm and checkpoint provenance.

# Conservative causal-memory residual training protocol
# - parent: Nolane-R1.6-NS2-CounterfactualWorld.pt
# - 80 causal train worlds, 662 total teacher transitions, 582 evidence-bearing transitions
# - frozen parent policy/world model
# - trainable: causal_memory_policy_key (640x640, bias=False) + causal_memory_policy_scale
# - key initialized to identity, scale initialized to zero
# - batched Stage-2 collection + batched perception cache
# - objective: CE(base_logits + evidence_gated_memory_bonus, teacher_action)
#              + 0.01 * bonus^2 + 0.01 * scale^2
# - optimizer: AdamW lr=8e-4, weight_decay=1e-4
# - 12 epochs
#
# The full executable source SHA and binary checkpoint SHA are recorded in the companion result file.
