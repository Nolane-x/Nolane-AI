from __future__ import annotations

from pathlib import Path
import torch
from cogcoder.neural_system2 import encode_action_descriptions, encode_structured_observation, structured_numeric_state_sketch
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_causal_memory import public_context_fingerprint
from cogcoder.r19_training import load_r19_delta
from cogcoder.r20_imagination import RecursiveImaginationPlanner


def _modules():
    root = Path(__file__).resolve().parents[1]
    parent, _ = load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt', expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt', expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')
    rollout, _ = load_r19_delta(root/'checkpoints/Nolane-R1.9-FGR-FrontierRollout.pt', expected_parent_checkpoint=root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt')
    parent.eval(); rollout.eval(); return parent, rollout


def _public_inputs(parent):
    task=make_r18_task('conditional_regimes','train',401); text=task.render_observation(); ids,values=encode_structured_observation(text,max_atoms=96); state=structured_numeric_state_sketch(ids.unsqueeze(0),values.unsqueeze(0),sketch_dim=parent.psr_sketch_dim).squeeze(0); context=public_context_fingerprint(text,dims=parent.conditional_law_context_dim); tokens=encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad(): action_embeddings=parent.action_encoder(tokens)[0]
    return state,context,action_embeddings,tuple(range(len(task.action_descriptions)))


def test_recursive_planner_supports_locked_depths_without_new_parameters():
    parent,rollout=_modules(); state,context,actions,legal=_public_inputs(parent); planner=RecursiveImaginationPlanner(parent,rollout,beam_width=3); result=planner.imagine_actions(state=state,context=context,action_embeddings=actions,legal_actions=legal,depths=(1,2,4,8,16)); assert set(result.depths)=={1,2,4,8,16}; assert result.parameter_count==0; assert result.used_hidden_task_fields is False


def test_recursive_planner_is_deterministic_bounded_and_legal():
    parent,rollout=_modules(); state,context,actions,legal=_public_inputs(parent); planner=RecursiveImaginationPlanner(parent,rollout,beam_width=2); a=planner.imagine_actions(state=state,context=context,action_embeddings=actions,legal_actions=legal,depths=(2,4)); b=planner.imagine_actions(state=state,context=context,action_embeddings=actions,legal_actions=legal,depths=(2,4)); assert a==b
    for depth,rows in a.by_depth.items():
        for row in rows: assert row.first_action in legal and len(row.actions)==depth and all(x in legal for x in row.actions) and len(row.beam_trace)<=planner.beam_width and 0.0<=row.uncertainty<=1.0


def test_recursive_planner_has_no_trainable_state_or_depth_specific_parameters():
    parent,rollout=_modules(); planner=RecursiveImaginationPlanner(parent,rollout,beam_width=2); assert not isinstance(planner,torch.nn.Module); assert not hasattr(planner,'parameters'); assert not hasattr(planner,'depth_embedding')
