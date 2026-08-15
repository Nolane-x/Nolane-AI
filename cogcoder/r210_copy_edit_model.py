from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor, nn
from torch.nn.utils.rnn import pack_padded_sequence

from .r210_copy_edit_features import canonicalize_source
from .r29_patch_model import PatchCandidate, RepositorySnapshot, apply_candidate

TOKEN_VOCAB: tuple[str, ...] = (
    'PAD','UNK','FUNC','RETURN','ARG0','ARG1','ARG2','ARG3','ARG4','ARG5',
    'IDENT','NUM_ZERO','NUM_ONE','NUM_NEG_ONE','NUM','TRUE','FALSE',
    'ADD','SUB','MUL','DIV','LT','LE','GT','GE','EQ','NE','AND','OR',
)
TOKEN_TO_ID = {token: index for index, token in enumerate(TOKEN_VOCAB)}


@dataclass(frozen=True, slots=True)
class CopyEditProposalConfig:
    vocab_size: int = len(TOKEN_VOCAB)
    embedding_dim: int = 32
    hidden_dim: int = 64
    evidence_dim: int = 16
    evidence_hidden_dim: int = 64
    fusion_dim: int = 96


class CopyEditProposalNet(nn.Module):
    """Compact language/task-id-free scorer for constrained source edits."""

    def __init__(self, config: CopyEditProposalConfig | None = None) -> None:
        super().__init__()
        self.config = config or CopyEditProposalConfig()
        c = self.config
        self.embedding = nn.Embedding(c.vocab_size, c.embedding_dim, padding_idx=0)
        self.sequence_gru = nn.GRU(c.embedding_dim, c.hidden_dim, batch_first=True)
        self.evidence_encoder = nn.Sequential(
            nn.Linear(c.evidence_dim, c.evidence_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(c.evidence_hidden_dim),
        )
        self.fusion = nn.Sequential(
            nn.Linear(c.hidden_dim * 2 + c.evidence_hidden_dim, c.fusion_dim),
            nn.GELU(),
            nn.LayerNorm(c.fusion_dim),
            nn.Linear(c.fusion_dim, c.fusion_dim),
            nn.GELU(),
        )
        self.scorer = nn.Linear(c.fusion_dim, 1)

    def _encode(self, tokens: Tensor) -> Tensor:
        if tokens.ndim != 2:
            raise ValueError('tokens must be [B,L]')
        lengths = (tokens != 0).sum(dim=1).clamp_min(1).cpu()
        embedded = self.embedding(tokens)
        packed = pack_padded_sequence(embedded, lengths, batch_first=True, enforce_sorted=False)
        _, hidden = self.sequence_gru(packed)
        return hidden[-1]

    def forward(
        self,
        *,
        context_tokens: Tensor,
        candidate_tokens: Tensor,
        evidence_features: Tensor,
        candidate_mask: Tensor,
    ) -> Tensor:
        c = self.config
        if context_tokens.ndim != 2:
            raise ValueError('context_tokens must be [B,L]')
        if candidate_tokens.ndim != 3:
            raise ValueError('candidate_tokens must be [B,A,L]')
        if evidence_features.ndim != 2 or evidence_features.shape[-1] != c.evidence_dim:
            raise ValueError(f'evidence_features must be [B,{c.evidence_dim}]')
        if candidate_mask.shape != candidate_tokens.shape[:2] or candidate_mask.dtype != torch.bool:
            raise ValueError('candidate_mask must be boolean [B,A]')
        batch, actions, length = candidate_tokens.shape
        if context_tokens.shape[0] != batch or evidence_features.shape[0] != batch:
            raise ValueError('all inputs must share batch size')
        if not bool(candidate_mask.any(dim=1).all()):
            raise ValueError('each item requires a legal candidate')

        context = self._encode(context_tokens)
        flat_candidates = candidate_tokens.reshape(batch * actions, length)
        candidate = self._encode(flat_candidates).reshape(batch, actions, -1)
        evidence = self.evidence_encoder(evidence_features)
        context_expand = context.unsqueeze(1).expand(-1, actions, -1)
        evidence_expand = evidence.unsqueeze(1).expand(-1, actions, -1)
        fused = self.fusion(torch.cat([context_expand, candidate, evidence_expand], dim=-1))
        logits = self.scorer(fused).squeeze(-1)
        return logits.masked_fill(~candidate_mask, float('-inf'))


def proposal_parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def token_ids(tokens: Sequence[str], *, max_length: int = 32) -> Tensor:
    ids = [TOKEN_TO_ID.get(token, TOKEN_TO_ID['UNK']) for token in tokens[:max_length]]
    ids.extend([0] * (max_length - len(ids)))
    return torch.tensor(ids, dtype=torch.long)


def rank_candidates(
    model: CopyEditProposalNet,
    source: str,
    *,
    language: str,
    target_path: str,
    candidates: Sequence[PatchCandidate],
    evidence_features: Tensor,
    max_length: int = 32,
) -> Tensor:
    if not candidates:
        raise ValueError('at least one candidate required')
    context = token_ids(canonicalize_source(source, language=language), max_length=max_length)
    snapshot = RepositorySnapshot({target_path: source})
    rows: list[Tensor] = []
    for candidate in candidates:
        patched = apply_candidate(snapshot, candidate).files[target_path]
        rows.append(token_ids(canonicalize_source(patched, language=language), max_length=max_length))
    candidate_tokens = torch.stack(rows).unsqueeze(0)
    evidence = evidence_features.reshape(1, -1).float()
    mask = torch.ones(1, len(candidates), dtype=torch.bool)
    model.eval()
    with torch.no_grad():
        logits = model(
            context_tokens=context.unsqueeze(0),
            candidate_tokens=candidate_tokens,
            evidence_features=evidence,
            candidate_mask=mask,
        )
    return logits.squeeze(0).cpu()
