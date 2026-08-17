from __future__ import annotations

import hashlib
import itertools

from cogcoder.r247_executable_patch_cegis import PatchTest, apply_patch_macros, solve_patch_with_sparse_tests
from cogcoder.r248_contextual_patch import (
    apply_contextual_patch_macros,
    enumerate_contextual_candidates,
    learn_contextual_patch_library,
)

HELDOUT_EPISODES=(1801,1811,1823,1831,1847,1861)
RENAMES=(('a','b','cap','alt'),('left','right','limit','other'))


def _source(fn,x,y,cap,alt, *, main_op='-', main_cmp='<', main_wrap=None):
    if main_wrap=='abs':
        main=f'abs({x}) {main_op} abs({y})'
    elif main_wrap=='neg':
        main=f'-{x} {main_op} -{y}'
    else:
        main=f'{x} {main_op} {y}'
    return f'''def {fn}({x}, {y}, {cap}, {alt}):
    shadow = {x} - {y}
    if shadow < {alt}:
        penalty = 1
    else:
        penalty = 2
    total = {main}
    if total {main_cmp} {cap}:
        return total + penalty
    return {cap} + 1 + shadow + penalty
'''


def _demo(kind, rename):
    x,y,cap,alt=RENAMES[rename]; fn=f'train_{kind}_{rename}'
    before=_source(fn,x,y,cap,alt)
    if kind.startswith('binop_'):
        op={'binop_add':'+','binop_mult':'*','binop_floordiv':'//','binop_mod':'%'}[kind]
        after=_source(fn,x,y,cap,alt,main_op=op)
    elif kind=='operands_abs':
        before=_source(fn,x,y,cap,alt,main_op='+')
        after=_source(fn,x,y,cap,alt,main_op='+',main_wrap='abs')
    elif kind=='operands_neg':
        before=_source(fn,x,y,cap,alt,main_op='+')
        after=_source(fn,x,y,cap,alt,main_op='+',main_wrap='neg')
    elif kind.startswith('cmp_'):
        cmp={'cmp_lte':'<=','cmp_gt':'>','cmp_gte':'>=','cmp_eq':'=='}[kind]
        after=_source(fn,x,y,cap,alt,main_cmp=cmp)
    else:
        raise ValueError(kind)
    return before,after


def training_demonstrations():
    kinds=('binop_add','binop_mult','binop_floordiv','binop_mod','operands_abs','operands_neg','cmp_lte','cmp_gt','cmp_gte','cmp_eq')
    return tuple(_demo(k,r) for k in kinds for r in range(2))


def learn_r248_library():
    lib=learn_contextual_patch_library(training_demonstrations())
    if len(lib)!=10 or any(m.support!=2 for m in lib):
        raise AssertionError((len(lib),[m.support for m in lib]))
    return lib


def _opaque(seed,role):
    return 'n_'+hashlib.sha256(f'r248|{seed}|{role}'.encode()).hexdigest()[:10]


def _episode(seed):
    fn='f_'+hashlib.sha256(f'r248|{seed}|fn'.encode()).hexdigest()[:12]
    x,y,cap,alt=(_opaque(seed,r) for r in ('x','y','cap','alt'))
    source=_source(fn,x,y,cap,alt)
    lib=learn_r248_library()
    essential=[]
    for m in lib:
        b=m.base
        if b.slot=='binop' and b.src=='Sub' and b.dst=='Add': essential.append(m)
        elif b.slot=='operand_wrapper' and b.dst=='abs': essential.append(m)
        elif b.slot=='compare' and b.src=='Lt' and b.dst=='LtE': essential.append(m)
    if len(essential)!=3: raise AssertionError('essential contextual macros')
    target=apply_contextual_patch_macros(source,essential)
    return source,target,tuple(sorted(m.macro_id for m in essential)),essential


def _compile(source):
    ns={'__builtins__':{'abs':abs,'max':max}}
    exec(compile(source,'<r248>','exec'),ns,ns)
    fns=[v for k,v in ns.items() if k.startswith('f_')]
    if len(fns)!=1: raise AssertionError('compile')
    return fns[0]


def _tests(seed,target):
    fn=_compile(target); out=[]
    for i,args in enumerate(itertools.product(range(-3,4),range(-3,4),range(0,7),range(-3,4))):
        out.append(PatchTest(f't:{seed}:{i:04d}',tuple(args),fn(*args)))
    return tuple(out)


def _order(seed,tests):
    return tuple(sorted((t.test_id for t in tests),key=lambda tid:hashlib.sha256(f'r248-order|{seed}|{tid}'.encode()).hexdigest()))


def _passes_all(source,tests):
    try: fn=_compile(source)
    except Exception: return False
    return all(fn(*t.args)==t.expected for t in tests)


def run_heldout_episode(seed):
    if seed not in HELDOUT_EPISODES: raise ValueError(seed)
    source,target,essential_ids,essential=_episode(seed)
    lib=learn_r248_library(); candidates=enumerate_contextual_candidates(source,lib)
    tests=_tests(seed,target); order=_order(seed,tests)
    receipt=solve_patch_with_sparse_tests(candidates,tests,initial_test_ids=order[:4],hidden_order=order,max_counterexamples=24)
    global_source=apply_patch_macros(source,[m.base for m in essential])
    global_exact=_passes_all(global_source,tests)
    selected=() if receipt.candidate is None else receipt.candidate.macro_ids
    return {
      'seed':seed,'exact':receipt.exact,'status':receipt.status,'learned_macros':len(lib),
      'initial_candidates':receipt.initial_candidate_count,'essential_macro_count':3,
      'selected_exact_macro_set':set(selected)==set(essential_ids),'global_r247_baseline_exact':global_exact,
      'initial_tests':receipt.initial_tests,'counterexamples_revealed':receipt.counterexamples_revealed,
      'observed_tests':len(receipt.observed_test_ids),'feedback_fraction':receipt.feedback_fraction,
      'candidate_test_evaluations':receipt.candidate_test_evaluations,
      'exhaustive_tests_verified':receipt.exhaustive_tests_verified,'test_suite_size':len(tests),
      'opaque_identifiers':all(tok not in source for tok in ('left','right','limit','train_','total = a')),
    }


def run_frozen_heldout():
    rows=[run_heldout_episode(s) for s in HELDOUT_EPISODES]
    summary={
      'episodes':len(rows),'exact':sum(r['exact'] for r in rows),'false_accepts':sum(not r['exact'] for r in rows),
      'learned_macros':rows[0]['learned_macros'],'initial_candidates':rows[0]['initial_candidates'],
      'essential_macro_count':3,'selected_exact_macro_set':sum(r['selected_exact_macro_set'] for r in rows),
      'global_r247_baseline_exact':sum(r['global_r247_baseline_exact'] for r in rows),
      'initial_tests_per_episode':4,'max_counterexamples_revealed':max(r['counterexamples_revealed'] for r in rows),
      'max_observed_tests':max(r['observed_tests'] for r in rows),'max_feedback_fraction':max(r['feedback_fraction'] for r in rows),
      'mean_feedback_fraction':sum(r['feedback_fraction'] for r in rows)/len(rows),
      'max_candidate_test_evaluations':max(r['candidate_test_evaluations'] for r in rows),
      'exhaustive_tests_per_episode':min(r['exhaustive_tests_verified'] for r in rows),'test_suite_size':rows[0]['test_suite_size'],
      'opaque_identifiers':all(r['opaque_identifiers'] for r in rows),
      'execution_mode':'context-localized compiled Python AST patches + executable tests'
    }
    gates={
      'all_exact':summary['exact']==6,'zero_false_accepts':summary['false_accepts']==0,
      'learned_distractor_library':summary['learned_macros']>=10,'three_macro_composition':summary['essential_macro_count']==3,
      'selected_exact_all':summary['selected_exact_macro_set']==6,'global_baseline_fails_all':summary['global_r247_baseline_exact']==0,
      'sparse_feedback_under_2_percent':summary['max_feedback_fraction']<=0.02,
      'final_exhaustive_execution':summary['exhaustive_tests_per_episode']==summary['test_suite_size']==2401,
      'opaque_identifiers':summary['opaque_identifiers'],
    }
    return {'schema_version':1,'milestone':'R2.48 Contextual Multi-Site Executable Patch Localization','heldout_episodes':list(HELDOUT_EPISODES),'rows':rows,'summary':summary,'gates':gates,'all_gates_pass':all(gates.values())}
