from __future__ import annotations

def decide_active_train_gate(full:dict,reset:dict,random_runs:list[dict])->dict[str,object]:
    if len(random_runs)!=5:raise ValueError('active train gate requires exactly five random repeats')
    random_mean=sum(float(row['solved']) for row in random_runs)/len(random_runs);full_solved=int(full['solved']);reset_solved=int(reset['solved']);gain=full_solved-reset_solved;full_families=dict(full.get('families',{}));reset_families=dict(reset.get('families',{}));family_preserved=bool(full_families) and set(full_families)==set(reset_families) and all(int(full_families[n])>=int(reset_families[n]) for n in full_families);accepted=bool(full_solved>random_mean and gain>=5 and family_preserved)
    return {'accepted':accepted,'full_solved':full_solved,'no_recurrence_solved':reset_solved,'random_mean_solved':random_mean,'recurrent_gain_over_reset':gain,'family_preserved':family_preserved,'full_families':full_families,'no_recurrence_families':reset_families}
