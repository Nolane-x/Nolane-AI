import torch

from cogcoder.r210_copy_edit_features import FailureProbe, encode_evidence, enumerate_copy_edit_candidates
from cogcoder.r210_copy_edit_model import (
    CopyEditProposalConfig,
    CopyEditProposalNet,
    proposal_parameter_count,
    rank_candidates,
)


def test_model_shapes_mask_and_parameter_ceiling():
    cfg = CopyEditProposalConfig()
    model = CopyEditProposalNet(cfg)
    context = torch.randint(0, cfg.vocab_size, (2, 12))
    candidates = torch.randint(0, cfg.vocab_size, (2, 4, 12))
    evidence = torch.randn(2, cfg.evidence_dim)
    mask = torch.tensor([[1,1,1,0],[1,1,1,1]], dtype=torch.bool)
    logits = model(context_tokens=context, candidate_tokens=candidates, evidence_features=evidence, candidate_mask=mask)
    assert logits.shape == (2,4)
    assert torch.isneginf(logits[0,3])
    assert proposal_parameter_count(model) <= 300_000


def test_rank_candidates_is_identifier_and_candidate_id_invariant():
    torch.manual_seed(210)
    model = CopyEditProposalNet()
    probes = (FailureProbe((3,2), 1, 5), FailureProbe((-1,4), -5, 3))
    evidence = encode_evidence(probes)
    src_a = 'def f(left, right):\n    return left - right\n'
    src_b = 'def f(foo, bar):\n    return foo - bar\n'
    a = enumerate_copy_edit_candidates(src_a, language='python', target_path='app.py', candidate_prefix='a-')
    b = enumerate_copy_edit_candidates(src_b, language='python', target_path='app.py', candidate_prefix='b-')
    scores_a = rank_candidates(model, src_a, language='python', target_path='app.py', candidates=a, evidence_features=evidence)
    scores_b = rank_candidates(model, src_b, language='python', target_path='app.py', candidates=b, evidence_features=evidence)
    assert torch.allclose(scores_a, scores_b)
