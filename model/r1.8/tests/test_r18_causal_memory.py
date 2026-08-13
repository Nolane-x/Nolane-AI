import json

import torch

from cogcoder.r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint


def _obs(key: str, value: str) -> str:
    return json.dumps({"benchmark":"nolane-figg18-v1","task_id":"example:123","step":4,"actions":["opaque actuator Nox-01","submit current hypothesis"],key:value,"state":[1,2,3],"last_event":"observable transition changed state","rule_hint":"action effects can depend on observable state and public regime"}, sort_keys=True)


def test_context_fingerprint_is_key_rename_invariant_and_value_sensitive():
    a=public_context_fingerprint(_obs("regime","amber")); b=public_context_fingerprint(_obs("mode","amber")); c=public_context_fingerprint(_obs("mode","violet"))
    assert a.shape==(64,); assert torch.equal(a,b); assert not torch.equal(a,c); assert torch.isfinite(a).all()


def test_memory_abstains_without_history_and_isolates_stale_contexts():
    mem=ConditionalEvidenceMemory(action_count=3,effect_dim=8); amber=public_context_fingerprint(_obs("regime","amber")); violet=public_context_fingerprint(_obs("regime","violet"))
    missing=mem.retrieve(1,amber); assert missing.count==0 and missing.reliable is False and torch.count_nonzero(missing.effect)==0
    effect=torch.tensor([1.0,0,0,0,0,0,0,0]); mem.update(1,amber,torch.zeros(8),effect)
    known=mem.retrieve(1,amber); stale=mem.retrieve(1,violet)
    assert known.count==1 and known.reliable and torch.allclose(known.effect,effect)
    assert stale.count==0 and stale.reliable is False and torch.count_nonzero(stale.effect)==0


def test_memory_averages_same_context_effects_and_tracks_consistency():
    mem=ConditionalEvidenceMemory(action_count=2,effect_dim=4); ctx=public_context_fingerprint(_obs("regime","cobalt"))
    mem.update(0,ctx,torch.tensor([0.0,0,0,0]),torch.tensor([1.0,0,0,0])); mem.update(0,ctx,torch.tensor([1.0,0,0,0]),torch.tensor([1.0,0,0,0]))
    stable=mem.retrieve(0,ctx); assert stable.count==2 and stable.consistency>0.99 and torch.allclose(stable.effect,torch.tensor([1.0,0,0,0]))
    mem.update(0,ctx,torch.tensor([2.0,0,0,0]),torch.tensor([-1.0,0,0,0])); noisy=mem.retrieve(0,ctx); assert noisy.count==3 and noisy.consistency<stable.consistency


def test_action_permutation_only_permutes_memory_slots():
    ctx=public_context_fingerprint(_obs("regime","amber")); effects=[torch.tensor([1.0,0,0]),torch.tensor([0.0,2,0]),torch.tensor([0.0,0,3])]
    base=ConditionalEvidenceMemory(action_count=3,effect_dim=3)
    for i,effect in enumerate(effects): base.update(i,ctx,torch.zeros(3),effect)
    perm=[2,0,1]; moved=ConditionalEvidenceMemory(action_count=3,effect_dim=3)
    for new_index,old_index in enumerate(perm): moved.update(new_index,ctx,torch.zeros(3),effects[old_index])
    for new_index,old_index in enumerate(perm):
        assert torch.allclose(moved.retrieve(new_index,ctx).effect,base.retrieve(old_index,ctx).effect)
        assert moved.retrieve(new_index,ctx).count==base.retrieve(old_index,ctx).count
