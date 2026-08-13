from __future__ import annotations
import hashlib,random,torch
from .neural_system2 import NeuralSystem2Workspace,encode_action_descriptions,encode_structured_observation,structured_numeric_delta_sketch
from .r18_causal_memory import ConditionalEvidenceMemory,public_context_fingerprint
from .r18_training import _public_state

def _context_key(context:torch.Tensor)->bytes:return context.detach().cpu().contiguous().numpy().tobytes()
def run_active_executive_episode(model:NeuralSystem2Workspace,task,*,mode:str='full',random_repeat:int=0)->dict[str,object]:
    if mode not in {'full','no_recurrence','random'}:raise ValueError('mode must be full, no_recurrence, or random')
    descriptions=tuple(str(item) for item in task.action_descriptions);action_count=len(descriptions);actions_taken=[];initial_budget=max(1.0,float(task.observe()['budget_remaining']))
    if mode=='random':
        rng=random.Random(int.from_bytes(hashlib.sha256(f'{task.task_id}|random|{int(random_repeat)}'.encode()).digest()[:8],'big'))
        while not task.done:
            a=rng.randrange(action_count);actions_taken.append(a);task.step(a)
        return {'task_id':task.task_id,'family':task.family,'mode':mode,'solved':bool(task.solved),'done':bool(task.done),'steps':len(actions_taken),'actions':actions_taken}
    model.eval();tokens=encode_action_descriptions(descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad():action_embeddings=model.action_encoder(tokens)[0].detach().cpu()
    evidence_memory=ConditionalEvidenceMemory(action_count=action_count,effect_dim=model.psr_sketch_dim);progress_by_context={};previous_feedback=torch.zeros(3);recurrent=model.init_r18_executive_state(batch_size=1)
    while not task.done:
        obs=task.observe();text=task.render_observation();before_ids,before_values,state=_public_state(text,sketch_dim=model.psr_sketch_dim);context=public_context_fingerprint(text,dims=model.conditional_law_context_dim);key=_context_key(context);progress_by_context.setdefault(key,[[0.0,0.0] for _ in range(action_count)]);progress_rows=progress_by_context[key];ev=[];meta=[]
        for i in range(action_count):
            lookup=evidence_memory.retrieve(i,context);ev.append(lookup.effect);meta.append(torch.tensor([min(1.0,lookup.count/4.0),lookup.consistency,lookup.context_similarity]))
        evidence=torch.stack(ev);evidence_meta=torch.stack(meta);progress_memory=torch.tensor([[float(delta),min(1.0,float(count)/4.0)] for delta,count in progress_rows])
        with torch.no_grad():
            law=model.conditional_law_scores(state.unsqueeze(0),context.unsqueeze(0),action_embeddings.unsqueeze(0),evidence.unsqueeze(0),evidence_meta.unsqueeze(0));hidden=law['hidden'];control=model.conditional_control_effect_scores(hidden);state_in=model.init_r18_executive_state(batch_size=1) if mode=='no_recurrence' else recurrent;out=model.r18_executive_step(state_sketch=state.unsqueeze(0),context_fingerprint=context.unsqueeze(0),progress=torch.tensor([[float(obs['progress_signal'])]]),budget_fraction=torch.tensor([[float(obs['budget_remaining'])/initial_budget]]),previous_feedback=previous_feedback.unsqueeze(0),conditional_hidden=hidden,control_effect=control,evidence_meta=evidence_meta.unsqueeze(0),progress_memory=progress_memory.unsqueeze(0),recurrent_state=state_in);chosen=int(out['logits'].argmax(-1));
            if mode=='full':recurrent=out['state'].detach()
        actions_taken.append(chosen);result=task.step(chosen);after_ids,after_values=encode_structured_observation(task.render_observation(),max_atoms=96);observed=structured_numeric_delta_sketch(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),sketch_dim=model.psr_sketch_dim).squeeze(0).detach().cpu();evidence_memory.update(chosen,context,state,observed);progress_rows[chosen][0]=float(result.progress_delta);progress_rows[chosen][1]+=1.0;previous_feedback=torch.tensor([float(result.progress_delta),float(result.information_gain),float(result.failed)])
    return {'task_id':task.task_id,'family':task.family,'mode':mode,'solved':bool(task.solved),'done':bool(task.done),'steps':len(actions_taken),'actions':actions_taken}
