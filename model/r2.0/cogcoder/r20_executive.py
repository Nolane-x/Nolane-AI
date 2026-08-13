from __future__ import annotations

import torch
from torch import Tensor, nn


class RecursiveImaginationExecutive(nn.Module):
    depth_values = (1, 2, 4, 8, 16)

    def __init__(self, *, state_dim: int = 128, context_dim: int = 64, action_dim: int = 640, effect_dim: int = 128, hidden_dim: int = 192) -> None:
        super().__init__()
        self.state_dim=int(state_dim); self.context_dim=int(context_dim); self.action_dim=int(action_dim); self.effect_dim=int(effect_dim); self.hidden_dim=int(hidden_dim)
        self.state_projection=nn.Linear(state_dim,96); self.context_projection=nn.Linear(context_dim,48); self.action_projection=nn.Linear(action_dim,160); self.effect_projection=nn.Linear(effect_dim,64); self.scalar_projection=nn.Linear(7,32)
        self.action_encoder=nn.Sequential(nn.Linear(96+48+160+64+64+32,hidden_dim),nn.GELU(),nn.LayerNorm(hidden_dim))
        self.global_projection=nn.Sequential(nn.Linear(96+48+32+hidden_dim,hidden_dim),nn.GELU(),nn.LayerNorm(hidden_dim))
        self.recurrent=nn.GRUCell(hidden_dim,hidden_dim); self.state_to_action=nn.Linear(hidden_dim,hidden_dim); self.action_score=nn.Linear(hidden_dim,1); self.stop_head=nn.Linear(hidden_dim,1); self.success_head=nn.Linear(hidden_dim,1); self.depth_head=nn.Linear(hidden_dim,len(self.depth_values))

    def init_state(self, *, batch_size:int, device=None, dtype=None)->Tensor:
        if batch_size<1: raise ValueError('batch_size must be positive')
        return torch.zeros(batch_size,self.hidden_dim,device=device,dtype=dtype or torch.float32)

    def forward(self, *, state:Tensor, context:Tensor, action_embeddings:Tensor, parent_effects:Tensor, imagined_effects:Tensor, imagined_uncertainty:Tensor, imagined_value:Tensor, progress:Tensor, budget_fraction:Tensor, previous_feedback:Tensor, recurrent_state:Tensor)->dict[str,Tensor]:
        if state.ndim!=2 or state.shape[-1]!=self.state_dim: raise ValueError('state must be [batch, state_dim]')
        batch=state.shape[0]
        if context.shape!=(batch,self.context_dim): raise ValueError('context must be [batch, context_dim]')
        if action_embeddings.ndim!=3 or action_embeddings.shape[0]!=batch or action_embeddings.shape[-1]!=self.action_dim: raise ValueError('action_embeddings must be [batch, actions, action_dim]')
        actions=action_embeddings.shape[1]; expected=(batch,actions,self.effect_dim)
        if parent_effects.shape!=expected or imagined_effects.shape!=expected: raise ValueError('effect tensors must be [batch, actions, effect_dim]')
        if imagined_uncertainty.shape!=(batch,actions) or imagined_value.shape!=(batch,actions): raise ValueError('imagined scalars must be [batch, actions]')
        if progress.shape!=(batch,1) or budget_fraction.shape!=(batch,1) or previous_feedback.shape!=(batch,3) or recurrent_state.shape!=(batch,self.hidden_dim): raise ValueError('global executive input shape mismatch')
        state_h=torch.tanh(self.state_projection(state)); context_h=torch.tanh(self.context_projection(context)); action_h=torch.tanh(self.action_projection(action_embeddings)); parent_h=torch.tanh(self.effect_projection(parent_effects)); imagined_h=torch.tanh(self.effect_projection(imagined_effects))
        scalar=torch.cat((progress,budget_fraction,previous_feedback,imagined_uncertainty.mean(dim=1,keepdim=True),imagined_value.mean(dim=1,keepdim=True)),dim=-1); scalar_h=torch.tanh(self.scalar_projection(scalar))
        features=torch.cat((state_h.unsqueeze(1).expand(batch,actions,-1),context_h.unsqueeze(1).expand(batch,actions,-1),action_h,parent_h,imagined_h,scalar_h.unsqueeze(1).expand(batch,actions,-1)),dim=-1)
        encoded=self.action_encoder(features); pooled=encoded.mean(dim=1); global_input=self.global_projection(torch.cat((state_h,context_h,scalar_h,pooled),dim=-1)); next_state=self.recurrent(global_input,recurrent_state); bias=self.state_to_action(next_state).unsqueeze(1)
        return {'action_logits':self.action_score(torch.tanh(encoded+bias)).squeeze(-1),'next_state':next_state,'stop_logit':self.stop_head(next_state).squeeze(-1),'success_probability':torch.sigmoid(self.success_head(next_state).squeeze(-1)),'depth_logits':self.depth_head(next_state)}


def r20_parameter_count(module:RecursiveImaginationExecutive)->int:
    return sum(p.numel() for p in module.parameters())
