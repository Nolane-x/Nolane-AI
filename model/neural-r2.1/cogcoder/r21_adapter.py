from __future__ import annotations

from typing import Any

from torch import Tensor, nn

from .r21_recursive_core import RecursiveLatentIntelligenceCore


class R20iRecursiveLatentPolicy(nn.Module):
    """Neural bridge: accepted R2.0e executive -> R2.1 recursive refiner.

    The parent executive remains a real neural submodule, so a later joint stage
    can fine-tune upstream representations end-to-end. R2.1 starts as an exact
    residual no-op for action, stop and success outputs.
    """

    def __init__(self, base_executive: nn.Module, recursive_core: RecursiveLatentIntelligenceCore) -> None:
        super().__init__()
        self.base_executive = base_executive
        self.recursive_core = recursive_core

    def forward(self, *, reasoning_steps: int = 4, **inputs: Tensor) -> dict[str, Any]:
        base = self.base_executive(**inputs)
        required = ("action_logits", "stop_logit", "success_probability", "next_state")
        missing = [key for key in required if key not in base]
        if missing:
            raise ValueError(f"base executive is missing required outputs: {missing}")

        refined = self.recursive_core(
            state=inputs["state"],
            context=inputs["context"],
            action_embeddings=inputs["action_embeddings"],
            parent_effects=inputs["parent_effects"],
            imagined_effects=inputs["imagined_effects"],
            evidence_effects=inputs["evidence_effects"],
            action_memory=inputs["action_memory"],
            imagined_uncertainty=inputs["imagined_uncertainty"],
            imagined_value=inputs["imagined_value"],
            base_action_logits=base["action_logits"],
            progress=inputs["progress"],
            budget_fraction=inputs["budget_fraction"],
            previous_feedback=inputs["previous_feedback"],
            base_stop_logit=base["stop_logit"],
            base_success_probability=base["success_probability"],
            reasoning_steps=reasoning_steps,
        )
        output: dict[str, Any] = dict(base)
        output.update(refined)
        output["base_action_logits"] = base["action_logits"]
        output["base_stop_logit"] = base["stop_logit"]
        output["base_success_probability"] = base["success_probability"]
        output["next_state"] = base["next_state"]
        output["reasoning_steps"] = int(reasoning_steps)
        return output
