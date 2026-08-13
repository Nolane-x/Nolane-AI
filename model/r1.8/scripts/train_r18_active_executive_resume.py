from __future__ import annotations
import json,random
from pathlib import Path
import torch
from cogcoder.neural_system2 import system2_parameter_count
from cogcoder.r17_training import checkpoint_metadata_for_report,load_r17_checkpoint,save_r17_checkpoint,sha256_file
from cogcoder.r18_executive_training import configure_executive_training,evaluate_executive_episodes,executive_trainable_state,restore_executive_trainable_state,train_executive_epoch
SEED=180818;EPOCHS=25;LR=1e-3;WEIGHT_DECAY=1e-4;EXPECTED_TRAINABLE=857_857;EXPECTED_EFFECTIVE=77_551_709

def _atomic_save(payload,path):
    tmp=path.with_suffix(path.suffix+'.tmp');torch.save(payload,tmp);tmp.replace(path)
def _finalize(root,model,state,parent,r12,r16):
    restore_executive_trainable_state(model,state['best_state']);result_path=root/'results/r1_8_active_executive_internal.json';output=root/'checkpoints/Nolane-R1.8-CCSM-ActiveExecutive.pt';protocol={'families':state['cache_metadata']['families'],'fit_indices':state['cache_metadata']['fit_indices'],'val_indices':state['cache_metadata']['val_indices'],'seed':SEED,'max_steps':state['cache_metadata']['max_steps'],'epochs':EPOCHS,'lr':LR,'weight_decay':WEIGHT_DECAY,'optimizer_updates_per_epoch':'one per cached episode','selection':'lowest validation cross_entropy','runtime':'process-isolated one-epoch resume with exact AdamW+Torch RNG state'};report={'version':'r1.8-active-executive-internal-v1','protocol':protocol,'control_effect_parent_sha256':sha256_file(parent),'candidate_effective_parameters':EXPECTED_EFFECTIVE,'trainable_parameters':EXPECTED_TRAINABLE,'initial_validation':state['initial_validation'],'best_epoch':state['best_epoch'],'best_validation':state['best_metrics'],'history':state['history']};meta=save_r17_checkpoint(output,model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'r1.8-verified-active-executive','control_effect_parent_sha256':sha256_file(parent),'protocol':protocol,'best_validation':state['best_metrics']});report['checkpoint']=checkpoint_metadata_for_report(meta);result_path.parent.mkdir(parents=True,exist_ok=True);result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({'event':'finalized','best_epoch':state['best_epoch'],'best_validation':state['best_metrics'],'checkpoint':report['checkpoint']},sort_keys=True))
def main():
    torch.set_num_threads(1);root=Path(__file__).resolve().parents[1];r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt';r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt';parent=root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt';cache_path=root/'cache/r18_active_executive_cache.pt';state_path=root/'cache/r18_active_executive_run_state.pt';cache=torch.load(cache_path,weights_only=False);meta=cache['metadata'];assert meta['parent_sha256']==sha256_file(parent) and meta['fit_indices']==[200,280] and meta['val_indices']==[280,300] and meta['fit_episodes']==320 and meta['val_episodes']==80;torch.manual_seed(SEED);random.seed(SEED);model,_=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16);configure_executive_training(model);assert sum(p.numel() for p in model.parameters() if p.requires_grad)==EXPECTED_TRAINABLE and 49_528_677+system2_parameter_count(model)==EXPECTED_EFFECTIVE;optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=LR,weight_decay=WEIGHT_DECAY)
    if state_path.exists():
        state=torch.load(state_path,weights_only=False);restore_executive_trainable_state(model,state['current_state']);optimizer.load_state_dict(state['optimizer']);torch.set_rng_state(state['torch_rng']);random.setstate(state['python_rng'])
    else:
        initial=evaluate_executive_episodes(model,cache['val']);state={'epoch':0,'initial_validation':initial,'best_epoch':0,'best_metrics':initial,'best_state':executive_trainable_state(model),'history':[],'cache_metadata':meta}
    if state['epoch']>=EPOCHS:_finalize(root,model,state,parent,r12,r16);return
    epoch=state['epoch']+1;loss=train_executive_epoch(model,cache['fit'],optimizer);metrics=evaluate_executive_episodes(model,cache['val']);row={'epoch':epoch,'train_loss':loss,**metrics};state['history'].append(row);state['epoch']=epoch
    if float(metrics['cross_entropy'])<float(state['best_metrics']['cross_entropy']):state['best_epoch']=epoch;state['best_metrics']=metrics;state['best_state']=executive_trainable_state(model)
    state['current_state']=executive_trainable_state(model);state['optimizer']=optimizer.state_dict();state['torch_rng']=torch.get_rng_state();state['python_rng']=random.getstate();_atomic_save(state,state_path);print(json.dumps({'event':'epoch_committed','epoch':epoch,'train_loss':loss,'validation':metrics,'best_epoch':state['best_epoch'],'best_cross_entropy':state['best_metrics']['cross_entropy']},sort_keys=True))
    if epoch>=EPOCHS:_finalize(root,model,state,parent,r12,r16)
if __name__=='__main__':main()
