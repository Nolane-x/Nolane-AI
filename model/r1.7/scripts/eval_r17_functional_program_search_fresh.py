from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import torch
from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_program_induction import infer_functional_program, execute_functional_program_hypothesis
from cogcoder.r17_training import load_r17_checkpoint, sha256_file

def main():
    torch.set_num_threads(4)
    root=Path(__file__).resolve().parents[1]
    r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'
    r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'
    parent=root/'checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt'
    model,meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16)
    model.eval()
    rows=[]; exact=solved=false_exact=0; eff_sum=0.0; eff_n=0
    template=defaultdict(lambda:{'solved':0,'total':0,'exact':0})
    for index in range(60):
        task=make_r17_task('composition_holdout','fresh',index)
        reference_actions=len(task.oracle_program)
        hyp=infer_functional_program(model,task.render_observation(),task.action_descriptions,max_horizon=4)
        result=execute_functional_program_hypothesis(task,hyp)
        ok=bool(result['solved']); ex=bool(hyp.exact); tid=index%6
        exact+=int(ex); solved+=int(ok); false_exact+=int(ex and not ok)
        slot=template[str(tid)];slot['solved']+=int(ok);slot['total']+=1;slot['exact']+=int(ex)
        if ok:
            e=min(1.0,reference_actions/max(1,int(result['pre_submit_actions'])));eff_sum+=e;eff_n+=1
        else:e=0.0
        rows.append({'index':index,'task_id':task.task_id,'template_id':tid,'exact':ex,'solved':ok,'sequence':list(hyp.sequence),'horizon':hyp.horizon,'orientation':hyp.orientation,'matched_elements':hyp.matched_elements,'total_elements':hyp.total_elements,'pre_submit_actions':int(result['pre_submit_actions']),'action_efficiency':e})
    total=len(rows)
    templates={k:{**v,'solve_rate':v['solved']/v['total'],'demo_exact_rate':v['exact']/v['total']} for k,v in sorted(template.items())}
    report={'version':'r1.7-functional-program-search-fresh-v1','protocol':{'split':'fresh','family':'composition_holdout','indices':[0,60],'max_horizon':4,'trainable_parameters':0},'operator_executor_sha256':sha256_file(parent),'operator_executor_candidate_effective_parameters':meta['candidate_effective_parameters'],'worlds':total,'demo_exact_rate':exact/total,'task_solve_rate':solved/total,'false_exact_rate':false_exact/total,'mean_action_efficiency':eff_sum/max(1,eff_n),'templates':templates,'rows':rows}
    report['accepted']=report['demo_exact_rate']>=.85 and report['task_solve_rate']>=.80 and report['false_exact_rate']<=.05 and all(v['solve_rate']>=.70 for v in templates.values())
    path=root/'results/r1_7_functional_program_search_fresh.json';path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ['worlds','demo_exact_rate','task_solve_rate','false_exact_rate','mean_action_efficiency','accepted']},sort_keys=True));print(json.dumps(templates,sort_keys=True))
    if not report['accepted']: raise SystemExit(2)
if __name__=='__main__': main()
