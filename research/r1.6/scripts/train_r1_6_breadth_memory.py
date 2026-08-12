from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import argparse, math, random
import torch
import torch.nn.functional as F
from cogcoder.edit_training import load_stage2_checkpoint
from cogcoder.frontier_interactive import build_split
from cogcoder.neural_system2 import NeuralSystem2Workspace, structured_numeric_delta_sketch
from cogcoder.neural_system2_curriculum import FrozenStage2ObservationEncoder, collect_teacher_trajectories_batched
from cogcoder.neural_system2_training import load_system2_checkpoint, save_system2_checkpoint

@dataclass
class CachedStep:
    context: torch.Tensor
    actions: torch.Tensor
    ids: torch.Tensor
    values: torch.Tensor
    label: int
    feedback: torch.Tensor
    cf_progress: torch.Tensor
    cf_information: torch.Tensor
    cf_failure: torch.Tensor


def cache_trajectories(model, trajectories):
    rows=[]; model.eval()
    with torch.no_grad():
        for tr in trajectories:
            seq=[]
            for s in tr.steps:
                latent=s.latent.unsqueeze(0)
                obs=s.observation_tokens.unsqueeze(0)
                ids=s.structured_ids.unsqueeze(0); vals=s.structured_values.unsqueeze(0)
                context=model.latent_norm(
                    model.latent_projection(latent)
                    + model.observation_encoder(obs)
                    + model.structured_observation_encoder(ids, vals)
                )[0]
                actions=model.action_encoder(s.action_tokens.unsqueeze(0))[0]
                seq.append(CachedStep(
                    context=context.detach(), actions=actions.detach(), ids=s.structured_ids,
                    values=s.structured_values, label=int(s.action_label),
                    feedback=torch.tensor([s.progress_target,s.information_target,s.failure_target],dtype=torch.float32),
                    cf_progress=s.counterfactual_progress, cf_information=s.counterfactual_information,
                    cf_failure=s.counterfactual_failure,
                ))
            rows.append(seq)
    return rows


def trajectory_loss(model, seq, refinement_steps=1):
    slots=None; memory=None; counts=None; last_context=None; last_ids=None; last_values=None
    prev_action=None; prev_feedback=None
    losses=[]; correct=0
    for st in seq:
        context=st.context.unsqueeze(0); actions=st.actions.unsqueeze(0); ac=actions.shape[1]
        if slots is None:
            slots=model.learned_slots.unsqueeze(0) + torch.tanh(model.slot_condition(context)).unsqueeze(1)
            memory=torch.zeros(1,ac,model.action_memory_dim)
            counts=torch.zeros(1,ac)
        else:
            slots=slots + 0.25*torch.tanh(model.slot_condition(context)).unsqueeze(1)
            sketch=structured_numeric_delta_sketch(last_ids.unsqueeze(0),last_values.unsqueeze(0),st.ids.unsqueeze(0),st.values.unsqueeze(0),sketch_dim=128)
            structured_effect=model.structured_delta_encoder(sketch)
            effect=torch.tanh(model.effect_encoder(context-last_context)+model.feedback_encoder(prev_feedback.unsqueeze(0))+structured_effect)
            old=memory[:,prev_action]
            updated=model.action_memory_update(effect,old)
            selector=F.one_hot(torch.tensor([prev_action]),num_classes=ac).float().unsqueeze(-1)
            memory=memory*(1.0-selector)+updated.unsqueeze(1)*selector
            counts=counts+selector.squeeze(-1)
        enriched=actions+model.action_memory_projection(memory)
        slots=model._refine(context,enriched,slots,refinement_steps=refinement_steps)
        thought=slots.mean(1)
        semantic=(model.policy_query(thought).unsqueeze(1)*model.action_key(enriched)).sum(-1)/math.sqrt(model.workspace_dim)
        ex=context.unsqueeze(1).expand_as(enriched)
        rel=torch.cat((ex,enriched,ex*enriched,torch.abs(ex-enriched)),dim=-1)
        context_logits=model.context_action_scorer(rel).squeeze(-1)
        world=torch.tanh(model.world_state(thought).unsqueeze(1)+model.world_action(enriched)); world=model.world_norm(world)
        progress=torch.tanh(model.progress_head(world).squeeze(-1)); info=torch.sigmoid(model.information_head(world).squeeze(-1)); fail=torch.sigmoid(model.failure_head(world).squeeze(-1))
        residual=model.policy_residual(world).squeeze(-1); uncertainty=torch.sigmoid(model.uncertainty_head(thought).squeeze(-1))
        exploration=F.softplus(model.exploration_scale)*torch.exp(-counts)*(0.5+1.5*uncertainty).unsqueeze(1)
        logits=semantic+context_logits+residual+model.imagination_utility(progress,info,fail)+exploration
        label=torch.tensor([st.label])
        action_loss=F.cross_entropy(logits,label)
        world_loss=0.35*F.mse_loss(progress[0],st.cf_progress)+0.25*F.binary_cross_entropy(info[0],st.cf_information)+0.55*F.binary_cross_entropy(fail[0],st.cf_failure)
        losses.append(action_loss+world_loss)
        correct+=int(logits.argmax(-1).item()==st.label)
        prev_action=st.label; prev_feedback=st.feedback; last_context=context; last_ids=st.ids; last_values=st.values
    return torch.stack(losses).mean(), correct, len(seq)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--epochs',type=int,default=1); ap.add_argument('--per-family',type=int,default=20); ap.add_argument('--seed',type=int,default=624)
    args=ap.parse_args(); torch.manual_seed(args.seed); random.seed(args.seed)
    root=Path(__file__).resolve().parents[1]; parent=root/'checkpoints/Nolane-R1.6-NS2-CounterfactualWorld.pt'; r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'
    model,_=load_system2_checkpoint(parent,expected_r1_2_checkpoint=r12)
    trunk,tok,_=load_stage2_checkpoint(root/'checkpoints/Nolane-48M-Stage2-Policy.pt'); enc=FrozenStage2ObservationEncoder(trunk,tok,max_length=96)
    trajectories=collect_teacher_trajectories_batched(build_split('train',per_family=args.per_family),enc,encoding_batch_size=32)
    cached=cache_trajectories(model,trajectories)
    for p in model.parameters(): p.requires_grad=False
    fast_modules=[model.structured_delta_encoder,model.effect_encoder,model.feedback_encoder,model.action_memory_update,model.action_memory_projection]
    consequence_modules=[model.action_key,model.world_action,model.progress_head,model.information_head,model.failure_head,model.policy_residual]
    for module in fast_modules+consequence_modules:
        for p in module.parameters(): p.requires_grad=True
    fast_params=[p for module in fast_modules for p in module.parameters()]; consequence_params=[p for module in consequence_modules for p in module.parameters()]
    opt=torch.optim.AdamW([{'params':fast_params,'lr':2.5e-4},{'params':consequence_params,'lr':1.0e-4}],weight_decay=1e-4)
    trainable=sum(p.numel() for p in model.parameters() if p.requires_grad)
    print({'trajectories':len(cached),'steps':sum(len(x) for x in cached),'trainable_parameters':trainable},flush=True)
    for epoch in range(1,args.epochs+1):
        order=list(range(len(cached))); random.shuffle(order); total=0; corr=0; lsum=0.
        for idx in order:
            opt.zero_grad(set_to_none=True); loss,c,n=trajectory_loss(model,cached[idx],refinement_steps=1); loss.backward(); torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.0); opt.step(); total+=n; corr+=c; lsum+=float(loss.item())*n
        print({'epoch':epoch,'loss':lsum/total,'action_accuracy':corr/total,'delta_norm':float(model.structured_delta_encoder.weight.detach().norm())},flush=True)
    out=root/'checkpoints/Nolane-R1.6-NS2-BreadthMemory.pt'
    meta=save_system2_checkpoint(out,model,r1_2_checkpoint=r12,report={'experiment':'breadth-first-memory-world-plan','parent':parent.name,'train_tasks':args.per_family*3,'train_steps':sum(len(x) for x in cached),'fresh_opened':False})
    print({'saved':str(out),'sha256':meta['sha256']},flush=True)
if __name__=='__main__': main()
