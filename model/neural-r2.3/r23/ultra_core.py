from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import Tensor, nn
import torch.nn.functional as F


class SwiGLU(nn.Module):
    def __init__(self, dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.gate = nn.Linear(dim, hidden_dim, bias=False)
        self.value = nn.Linear(dim, hidden_dim, bias=False)
        self.out = nn.Linear(hidden_dim, dim, bias=False)

    def forward(self, x: Tensor) -> Tensor:
        return self.out(F.silu(self.gate(x)) * self.value(x))


class SharedScaledReasoningCell(nn.Module):
    """One set-equivariant recurrent cell reused at every reasoning depth."""

    def __init__(self, latent_dim: int, n_heads: int, ff_mult: int) -> None:
        super().__init__()
        if latent_dim % n_heads:
            raise ValueError("latent_dim must be divisible by n_heads")
        self.latent_dim = int(latent_dim)
        self.n_heads = int(n_heads)
        self.head_dim = latent_dim // n_heads
        self.query = nn.Linear(latent_dim, latent_dim, bias=False)
        self.key = nn.Linear(latent_dim, latent_dim, bias=False)
        self.value = nn.Linear(latent_dim, latent_dim, bias=False)
        self.attention_out = nn.Linear(latent_dim, latent_dim, bias=False)
        self.depth_projection = nn.Linear(6, latent_dim, bias=False)
        self.pre_recurrent_norm = nn.LayerNorm(latent_dim)
        self.recurrent = nn.GRUCell(latent_dim, latent_dim)
        self.global_norm = nn.LayerNorm(latent_dim)
        self.global_ff = SwiGLU(latent_dim, latent_dim * ff_mult)
        self.global_gate = nn.Parameter(torch.tensor(-0.5))
        self.state_to_action = nn.Linear(latent_dim, latent_dim, bias=False)
        self.action_norm = nn.LayerNorm(latent_dim)
        self.action_ff = SwiGLU(latent_dim, latent_dim * ff_mult)
        self.action_gate = nn.Parameter(torch.tensor(-0.5))

    @staticmethod
    def _depth_features(step: int, *, device: torch.device, dtype: torch.dtype) -> Tensor:
        t = torch.tensor(float(step + 1), device=device, dtype=dtype)
        logt = torch.log1p(t)
        return torch.stack((1.0 / t, t / (t + 1.0), logt / 4.0, torch.sin(logt), torch.cos(logt), 1.0 / torch.sqrt(t)))

    def forward(self, latent: Tensor, action_tokens: Tensor, *, step: int) -> tuple[Tensor, Tensor]:
        batch, actions, dim = action_tokens.shape
        q = self.query(latent).view(batch, self.n_heads, self.head_dim)
        k = self.key(action_tokens).view(batch, actions, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.value(action_tokens).view(batch, actions, self.n_heads, self.head_dim).transpose(1, 2)
        scores = torch.einsum("bhd,bhad->bha", q, k) / math.sqrt(float(self.head_dim))
        weights = torch.softmax(scores, dim=-1)
        attended = torch.einsum("bha,bhad->bhd", weights, v).reshape(batch, dim)
        depth = self.depth_projection(self._depth_features(step, device=latent.device, dtype=latent.dtype)).unsqueeze(0)
        recurrent_input = self.pre_recurrent_norm(latent + self.attention_out(attended) + depth)
        latent = self.recurrent(recurrent_input, latent)
        delta = self.global_ff(self.global_norm(latent))
        latent = self.global_norm(latent + torch.sigmoid(self.global_gate) * delta)
        broadcast = self.state_to_action(latent).unsqueeze(1) + depth.unsqueeze(1)
        action_hidden = self.action_norm(action_tokens + broadcast)
        action_delta = self.action_ff(action_hidden)
        action_tokens = self.action_norm(action_tokens + torch.sigmoid(self.action_gate) * action_delta + 0.1 * broadcast)
        return latent, action_tokens


@dataclass(frozen=True)
class R22ScaledArchitecture:
    state_dim: int = 128
    context_dim: int = 64
    action_dim: int = 640
    effect_dim: int = 128
    action_memory_dim: int = 7
    latent_dim: int = 512
    n_heads: int = 8
    ff_mult: int = 2


class ScaledRecursiveDistilledReasoner(nn.Module):
    """Wide weight-shared neural reasoner with fail-closed learned delegation."""

    def __init__(self, *, state_dim: int = 128, context_dim: int = 64, action_dim: int = 640, effect_dim: int = 128, action_memory_dim: int = 7, latent_dim: int = 512, n_heads: int = 8, ff_mult: int = 2) -> None:
        super().__init__()
        if min(state_dim, context_dim, action_dim, effect_dim, action_memory_dim, latent_dim, n_heads, ff_mult) < 1:
            raise ValueError("all architecture dimensions must be positive")
        if latent_dim % n_heads:
            raise ValueError("latent_dim must be divisible by n_heads")
        self.state_dim = int(state_dim); self.context_dim = int(context_dim); self.action_dim = int(action_dim); self.effect_dim = int(effect_dim); self.action_memory_dim = int(action_memory_dim); self.latent_dim = int(latent_dim); self.n_heads = int(n_heads); self.ff_mult = int(ff_mult)
        self.action_projection = nn.Linear(action_dim, latent_dim, bias=False)
        self.parent_effect_projection = nn.Linear(effect_dim, latent_dim, bias=False)
        self.imagined_effect_projection = nn.Linear(effect_dim, latent_dim, bias=False)
        self.evidence_effect_projection = nn.Linear(effect_dim, latent_dim, bias=False)
        self.action_memory_projection = nn.Linear(action_memory_dim, latent_dim, bias=False)
        self.action_scalar_projection = nn.Linear(4, latent_dim, bias=False)
        self.action_anchor_norm = nn.LayerNorm(latent_dim)
        self.state_projection = nn.Linear(state_dim, latent_dim, bias=False)
        self.context_projection = nn.Linear(context_dim, latent_dim, bias=False)
        self.global_scalar_projection = nn.Linear(9, latent_dim, bias=False)
        self.initial_norm = nn.LayerNorm(latent_dim)
        self.reasoning_cell = SharedScaledReasoningCell(latent_dim, n_heads, ff_mult)
        self.action_residual_head = nn.Linear(latent_dim, 1)
        self.action_value_head = nn.Sequential(nn.Linear(latent_dim, latent_dim // 2), nn.GELU(), nn.LayerNorm(latent_dim // 2), nn.Linear(latent_dim // 2, 1))
        self.repair_gate_head = nn.Sequential(nn.Linear(latent_dim * 3 + 4, latent_dim), nn.GELU(), nn.LayerNorm(latent_dim), nn.Linear(latent_dim, 1))
        self.parent_correct_head = nn.Linear(latent_dim, 1)
        self.action_compatibility_head = nn.Sequential(nn.Linear(latent_dim, latent_dim // 2), nn.GELU(), nn.LayerNorm(latent_dim // 2), nn.Linear(latent_dim // 2, 1))
        self.progress_head = nn.Linear(latent_dim, 1); self.uncertainty_head = nn.Linear(latent_dim, 1); self.stop_head = nn.Linear(latent_dim, 1); self.success_head = nn.Linear(latent_dim, 1); self.ponder_head = nn.Linear(latent_dim, 1)
        nn.init.zeros_(self.action_residual_head.weight); nn.init.zeros_(self.action_residual_head.bias)
        nn.init.zeros_(self.stop_head.weight); nn.init.zeros_(self.stop_head.bias); nn.init.zeros_(self.success_head.weight); nn.init.zeros_(self.success_head.bias)
        nn.init.zeros_(self.repair_gate_head[-1].weight); nn.init.constant_(self.repair_gate_head[-1].bias, -6.0)
        nn.init.zeros_(self.action_compatibility_head[-1].weight); nn.init.constant_(self.action_compatibility_head[-1].bias, 4.0)

    def architecture(self) -> dict[str, int]:
        return {"state_dim": self.state_dim, "context_dim": self.context_dim, "action_dim": self.action_dim, "effect_dim": self.effect_dim, "action_memory_dim": self.action_memory_dim, "latent_dim": self.latent_dim, "n_heads": self.n_heads, "ff_mult": self.ff_mult}

    def _validate(self, **kw: Tensor | int) -> tuple[int, int]:
        state=kw["state"]; context=kw["context"]; action_embeddings=kw["action_embeddings"]; reasoning_steps=kw["reasoning_steps"]
        assert isinstance(state, Tensor) and isinstance(context, Tensor) and isinstance(action_embeddings, Tensor)
        if not isinstance(reasoning_steps, int) or isinstance(reasoning_steps, bool) or reasoning_steps < 1: raise ValueError("reasoning_steps must be a positive integer")
        if state.ndim != 2 or state.shape[-1] != self.state_dim: raise ValueError("state must be [batch, state_dim]")
        batch=state.shape[0]
        if context.shape != (batch,self.context_dim): raise ValueError("context must be [batch, context_dim]")
        if action_embeddings.ndim != 3 or action_embeddings.shape[0] != batch or action_embeddings.shape[-1] != self.action_dim: raise ValueError("action_embeddings must be [batch, actions, action_dim]")
        actions=action_embeddings.shape[1]
        for name in ("parent_effects","imagined_effects","evidence_effects"):
            v=kw[name]; assert isinstance(v, Tensor)
            if v.shape != (batch,actions,self.effect_dim): raise ValueError(f"{name} must be [batch, actions, effect_dim]")
        am=kw["action_memory"]; iu=kw["imagined_uncertainty"]; iv=kw["imagined_value"]; bal=kw["base_action_logits"]
        assert isinstance(am, Tensor) and isinstance(iu, Tensor) and isinstance(iv, Tensor) and isinstance(bal, Tensor)
        if am.shape != (batch,actions,self.action_memory_dim): raise ValueError("action_memory must be [batch, actions, action_memory_dim]")
        if iu.shape != (batch,actions) or iv.shape != (batch,actions) or bal.shape != (batch,actions): raise ValueError("action scalar shape mismatch")
        for name,shape in (("progress",(batch,1)),("budget_fraction",(batch,1)),("previous_feedback",(batch,3)),("base_stop_logit",(batch,)),("base_success_probability",(batch,))):
            v=kw[name]; assert isinstance(v, Tensor)
            if v.shape != shape: raise ValueError(f"{name} has invalid shape")
        return batch,actions

    @staticmethod
    def _policy_stats(base_action_logits: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        actions=base_action_logits.shape[-1]; centered=base_action_logits-base_action_logits.mean(-1,keepdim=True); scale=torch.ones_like(centered[...,:1]) if actions==1 else base_action_logits.std(-1,keepdim=True).clamp_min(1e-3); z=centered/scale; prob=torch.softmax(base_action_logits,dim=-1); entropy=-(prob*torch.log(prob.clamp_min(1e-8))).sum(-1,keepdim=True)
        margin=torch.ones_like(entropy) if actions==1 else (lambda t:t[:,:1]-t[:,1:2])(torch.topk(base_action_logits,k=2,dim=-1).values)
        return z,prob,entropy,margin

    def forward(self, *, state: Tensor, context: Tensor, action_embeddings: Tensor, parent_effects: Tensor, imagined_effects: Tensor, evidence_effects: Tensor, action_memory: Tensor, imagined_uncertainty: Tensor, imagined_value: Tensor, base_action_logits: Tensor, progress: Tensor, budget_fraction: Tensor, previous_feedback: Tensor, base_stop_logit: Tensor, base_success_probability: Tensor, reasoning_steps: int = 1) -> dict[str, Tensor]:
        self._validate(state=state,context=context,action_embeddings=action_embeddings,parent_effects=parent_effects,imagined_effects=imagined_effects,evidence_effects=evidence_effects,action_memory=action_memory,imagined_uncertainty=imagined_uncertainty,imagined_value=imagined_value,base_action_logits=base_action_logits,progress=progress,budget_fraction=budget_fraction,previous_feedback=previous_feedback,base_stop_logit=base_stop_logit,base_success_probability=base_success_probability,reasoning_steps=reasoning_steps)
        z,base_prob,entropy,margin=self._policy_stats(base_action_logits); action_scalars=torch.stack((imagined_uncertainty,imagined_value,z,base_prob),dim=-1)
        action_tokens=self.action_anchor_norm(self.action_projection(action_embeddings)+self.parent_effect_projection(parent_effects)+self.imagined_effect_projection(imagined_effects)+self.evidence_effect_projection(evidence_effects)+self.action_memory_projection(action_memory)+self.action_scalar_projection(action_scalars))
        success=base_success_probability.clamp(1e-6,1-1e-6); success_logit=torch.logit(success); global_scalars=torch.cat((progress,budget_fraction,previous_feedback,base_stop_logit[:,None],success[:,None],entropy,margin),dim=-1)
        latent=self.initial_norm(self.state_projection(state)+self.context_projection(context)+self.global_scalar_projection(global_scalars)+action_tokens.mean(dim=1))
        logits_traj=[];gate_traj=[];value_traj=[];latent_traj=[];ponder=[]
        for step in range(reasoning_steps):
            latent,action_tokens=self.reasoning_cell(latent,action_tokens,step=step); residual=self.action_residual_head(action_tokens).squeeze(-1); values=self.action_value_head(action_tokens).squeeze(-1); gate_features=torch.cat((latent,action_tokens.mean(1),action_tokens.max(1).values,progress,budget_fraction,entropy,margin),dim=-1); gate_logit=self.repair_gate_head(gate_features).squeeze(-1); raw_gate=torch.sigmoid(gate_logit); compatibility_logits=self.action_compatibility_head(action_tokens).squeeze(-1); parent_index=base_action_logits.argmax(dim=-1); parent_compatibility_logit=compatibility_logits.gather(1,parent_index[:,None]).squeeze(1); safety_factor=torch.sigmoid(-parent_compatibility_logit); gate=raw_gate*safety_factor; logits=base_action_logits+gate[:,None]*residual
            logits_traj.append(logits);gate_traj.append(gate);value_traj.append(values);latent_traj.append(latent);ponder.append(self.ponder_head(latent).squeeze(-1))
        residual=self.action_residual_head(action_tokens).squeeze(-1); values=self.action_value_head(action_tokens).squeeze(-1); gate_features=torch.cat((latent,action_tokens.mean(1),action_tokens.max(1).values,progress,budget_fraction,entropy,margin),dim=-1); gate_logit=self.repair_gate_head(gate_features).squeeze(-1); raw_gate=torch.sigmoid(gate_logit); parent_correct_logit=self.parent_correct_head(latent).squeeze(-1); compatibility_logits=self.action_compatibility_head(action_tokens).squeeze(-1); parent_index=base_action_logits.argmax(dim=-1); parent_compatibility_logit=compatibility_logits.gather(1,parent_index[:,None]).squeeze(1); safety_factor=torch.sigmoid(-parent_compatibility_logit); gate=raw_gate*safety_factor; final_residual=gate[:,None]*residual
        return {"action_logits":base_action_logits+final_residual,"proposal_action_logits":base_action_logits+residual,"action_logit_residual":final_residual,"raw_action_residual":residual,"action_value":values,"override_gate":gate,"raw_override_gate":raw_gate,"safety_factor":safety_factor,"override_gate_logit":gate_logit,"parent_correct_logit":parent_correct_logit,"action_compatibility_logits":compatibility_logits,"parent_compatibility_logit":parent_compatibility_logit,"progress_prediction":torch.sigmoid(self.progress_head(latent)).squeeze(-1),"uncertainty":torch.sigmoid(self.uncertainty_head(latent)).squeeze(-1),"stop_logit":base_stop_logit+self.stop_head(latent).squeeze(-1),"success_probability":torch.sigmoid(success_logit+self.success_head(latent).squeeze(-1)),"ponder_logit":self.ponder_head(latent).squeeze(-1),"latent_state":latent,"action_logits_trajectory":torch.stack(logits_traj,dim=1),"override_gate_trajectory":torch.stack(gate_traj,dim=1),"action_value_trajectory":torch.stack(value_traj,dim=1),"latent_trajectory":torch.stack(latent_traj,dim=1),"ponder_logits_trajectory":torch.stack(ponder,dim=1)}


def r22_parameter_count(module: nn.Module) -> int:
    return sum(p.numel() for p in module.parameters())
