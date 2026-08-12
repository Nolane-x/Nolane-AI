from __future__ import annotations

import argparse, copy, random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn.functional as F

from cogcoder.edit_training import load_stage2_checkpoint
from cogcoder.frontier_interactive import FAMILIES, build_split
from cogcoder.neural_system2 import contrastive_action_effect_sketch
from cogcoder.neural_system2_curriculum import FrozenStage2ObservationEncoder, collect_teacher_trajectories_batched
from cogcoder.neural_system2_training import load_system2_checkpoint, save_system2_checkpoint


@dataclass
class BinderRow:
    family: str
    atoms: torch.Tensor
    mask: torch.Tensor
    effects: torch.Tensor
    counts: torch.Tensor
    base_logits: torch.Tensor
    label: int


def select_tasks(start: int, count: int):
    pool=build_split('train',per_family=start+count); by=defaultdict(list)
    for task in pool: by[task.family].append(task)
    return [copy.deepcopy(by[f][i]) for f in FAMILIES for i in range(start,start+count)]


def cache_rows(model, tasks, encoder):
    trajectories=collect_teacher_trajectories_batched(tasks,encoder,encoding_batch_size=32)
    rows=[]; model.eval()
    with torch.no_grad():
        for tr in trajectories:
            state=None; prev=None; fb=None
            for st in tr.steps:
                ids=st.structured_ids.unsqueeze(0); vals=st.structured_values.unsqueeze(0)
                atoms,mask=model.structured_observation_encoder.encode_atoms(ids,vals)
                out=model(
                    st.latent.unsqueeze(0), st.action_tokens.unsqueeze(0), state=state,
                    observation_tokens=st.observation_tokens.unsqueeze(0),
                    structured_ids=ids, structured_values=vals,
                    previous_action=prev, previous_feedback=fb,
                    refinement_steps=1, policy_mode='full',
                )
                effects=contrastive_action_effect_sketch(
                    out.state.action_effect_sketch, out.state.action_counts
                )
                rows.append(BinderRow(
                    family=tr.family,
                    atoms=atoms[0].cpu(), mask=mask[0].cpu(), effects=effects[0].cpu(),
                    counts=out.state.action_counts[0].cpu(), base_logits=out.action_logits[0].cpu(),
                    label=int(st.action_label),
                ))
                state=out.state; prev=int(st.action_label)
                fb=(float(st.progress_target),float(st.information_target),float(st.failure_target))
    return rows


def group(rows):
    out=defaultdict(list)
    for r in rows: out[int(r.base_logits.shape[0])].append(r)
    return out


def objective(model, groups):
    losses=[]; correct=0; total=0; fam=defaultdict(lambda:[0,0])
    for A,items in groups.items():
        atoms=torch.stack([r.atoms for r in items]); mask=torch.stack([r.mask for r in items])
        effects=torch.stack([r.effects for r in items]); counts=torch.stack([r.counts for r in items])
        base=torch.stack([r.base_logits for r in items]); labels=torch.tensor([r.label for r in items],dtype=torch.long)
        bonus=model.dual_role_causal_policy_bonus(atoms,mask,effects,counts)
        logits=base+bonus
        losses.append(F.cross_entropy(logits,labels))
        pred=logits.argmax(-1); correct+=int(pred.eq(labels).sum()); total+=len(items)
        for i,r in enumerate(items):
            fam[r.family][0]+=int(pred[i].item()==r.label); fam[r.family][1]+=1
    return torch.stack(losses).mean(), {'accuracy':correct/max(1,total),'rows':total,'family':{k:v[0]/v[1] for k,v in fam.items()}}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--fit-start',type=int,default=69); ap.add_argument('--fit-count',type=int,default=10); ap.add_argument('--val-start',type=int,default=79); ap.add_argument('--val-count',type=int,default=3); ap.add_argument('--epochs',type=int,default=80); ap.add_argument('--seed',type=int,default=16082)
    args=ap.parse_args(); torch.manual_seed(args.seed); random.seed(args.seed)
    root=Path(__file__).resolve().parents[1]; r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'; parent=root/'checkpoints/Nolane-R1.6-NS2-PSRPlanner.pt'
    model,_=load_system2_checkpoint(parent,expected_r1_2_checkpoint=r12)
    trunk,tok,_=load_stage2_checkpoint(root/'checkpoints/Nolane-48M-Stage2-Policy.pt'); encoder=FrozenStage2ObservationEncoder(trunk,tok,max_length=96)
    fit_rows=cache_rows(model,select_tasks(args.fit_start,args.fit_count),encoder); val_rows=cache_rows(model,select_tasks(args.val_start,args.val_count),encoder)
    fg=group(fit_rows); vg=group(val_rows)
    for p in model.parameters(): p.requires_grad=False
    network=[]
    for name,p in model.named_parameters():
        if name.startswith('dual_role_'):
            p.requires_grad=True; network.append(p)
    opt=torch.optim.AdamW([{'params':network,'lr':1.2e-3,'weight_decay':2e-4}])
    with torch.no_grad(): base_loss,base=objective(model,vg)
    print({'fit_rows':len(fit_rows),'val_rows':len(val_rows),'trainable':sum(p.numel() for p in network),'initial_val_loss':float(base_loss),'initial_val':base},flush=True)
    best=(float(base_loss),0,{k:v.detach().cpu().clone() for k,v in model.state_dict().items()},base)
    for epoch in range(1,args.epochs+1):
        opt.zero_grad(set_to_none=True); loss,fit=objective(model,fg)
        reg=1e-6*sum(p.square().mean() for p in network)
        (loss+reg).backward(); torch.nn.utils.clip_grad_norm_(network,1.0); opt.step()
        with torch.no_grad(): val_loss,val=objective(model,vg)
        if float(val_loss)<best[0] and val['accuracy']>=base['accuracy']:
            best=(float(val_loss),epoch,{k:v.detach().cpu().clone() for k,v in model.state_dict().items()},val)
        if epoch in {1,5,10,20,40,60,args.epochs}:
            print({'epoch':epoch,'fit_loss':float(loss.detach()),'fit':fit,'val_loss':float(val_loss),'val':val,'scale':float(torch.tanh(model.dual_role_causal_policy_scale).detach())},flush=True)
    model.load_state_dict(best[2]); print({'best_epoch':best[1],'best_val_loss':best[0],'best_val':best[3],'base_val':base,'scale':float(torch.tanh(model.dual_role_causal_policy_scale).detach())},flush=True)
    if best[1]>0:
        out=root/'checkpoints/Nolane-R1.6-NS2-DualRoleCausalBinder.pt'
        meta=save_system2_checkpoint(out,model,r1_2_checkpoint=r12,report={'experiment':'dual-role-effect-conditioned-structured-atom-causal-binder','parent':parent.name,'fit_start':args.fit_start,'fit_count':args.fit_count,'internal_val_start':args.val_start,'internal_val_count':args.val_count,'best_epoch':best[1],'base_internal_val':base,'best_internal_val':best[3],'fresh_opened':False})
        print({'saved':str(out),'sha256':meta['sha256'],'candidate_effective_parameters':meta['candidate_effective_parameters']},flush=True)
    else:
        print({'saved':None,'reason':'binder_did_not_improve_internal_validation'},flush=True)

if __name__=='__main__': main()
