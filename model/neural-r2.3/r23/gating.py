from __future__ import annotations

import torch
from torch import nn


def delegation_targets(parent_correct: torch.Tensor, proposal_correct: torch.Tensor, proposal_differs: torch.Tensor) -> torch.Tensor:
    if parent_correct.shape != proposal_correct.shape or parent_correct.shape != proposal_differs.shape:
        raise ValueError('delegation target tensors must have identical shapes')
    return (~parent_correct.bool()) & proposal_correct.bool() & proposal_differs.bool()


class HardDelegationWrapper(nn.Module):
    """Fail-closed delegation: preserve parent logits unless a frozen neural gate passes."""
    def __init__(self, reasoner: nn.Module, *, threshold: float) -> None:
        super().__init__()
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError('threshold must lie in [0, 1]')
        self.reasoner = reasoner
        self.threshold = float(threshold)

    def forward(self, **kw):
        output = self.reasoner(**kw)
        base = kw['base_action_logits']
        proposal = output['proposal_action_logits']
        parent_action = base.argmax(-1)
        proposal_action = proposal.argmax(-1)
        score = torch.sigmoid(output['override_gate_logit'])
        use = proposal_action.ne(parent_action) & score.ge(self.threshold)
        result = dict(output)
        result['hard_override_score'] = score
        result['hard_override'] = use
        result['action_logits'] = torch.where(use[:, None], proposal, base)
        return result
