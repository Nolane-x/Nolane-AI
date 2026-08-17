from __future__ import annotations

import hashlib, itertools

from cogcoder.r247_executable_patch_cegis import PatchTest, solve_patch_with_sparse_tests
from cogcoder.r248_contextual_patch import apply_contextual_patch_macros, learn_contextual_patch_library
from cogcoder.r249_relational_context import apply_relational_context_macros, enumerate_relational_candidates, learn_relational_context_library

HELDOUT_EPISODES=(1901,1913,1931,1949,1951,1973)
RENAMES=(('a','b','cap','alt'),('left','right','limit','other'))


def _expr(x,y,op,wrap=None):
    if wrap=='abs': return f'abs({x}) {op} abs({y})'
    if wrap=='neg': return f'-{x} {op} -{y}'
    return f'{x} {op} {y}'


def _source(fn,x,y,cap,alt,*,target_op='-',decoy_op='-',cmp='<',wrap=None,shape='direct'):
    target=_expr(x,y,target_op,wrap); decoy=_expr(x,y,decoy_op,None)
    lines=[f'def {fn}({x}, {y}, {cap}, {alt}):',f'    shadow = {decoy}', '    shadow_alias = shadow', f'    if shadow_alias < {alt}:','        penalty = 1','    else:','        penalty = 2',f'    core = {target}']
    if shape=='direct':
        lines += [f'    if core {cmp} {cap}:','        return core + penalty']
    elif shape=='alias':
        lines += ['    bridge = core',f'    if bridge {cmp} {cap}:','        out = bridge','        return out + penalty']
    elif shape=='nested':
        lines += ['    bridge1 = core','    bridge2 = bridge1',f'    if {cap} >= 0:',f'        if bridge2 {cmp} {cap}:','            out = bridge2','            return out + penalty']
    elif shape=='deep':
        lines += ['    bridge1 = core','    bridge2 = bridge1','    bridge3 = bridge2',f'    if {cap} >= 0:',f'        if bridge3 {cmp} {cap}:','            out1 = bridge3','            out2 = out1','            return out2 + penalty']
    else: raise ValueError(shape)
    lines += [f'    return {cap} + 1 + shadow + penalty']
    return '\n'.join(lines)+'\n'


def _demo(kind,rename,shape):
    x,y,cap,alt=RENAMES[rename]; fn=f'train_{kind}_{rename}_{shape}'
    if kind.startswith('binop_'):
        before=_source(fn,x,y,cap,alt,target_op='-',decoy_op='-',shape=shape)
        op={'binop_add':'+','binop_mult':'*','binop_floordiv':'//','binop_mod':'%'}[kind]
        after=_source(fn,x,y,cap,alt,target_op=op,decoy_op='-',shape=shape)
    elif kind.startswith('operands_'):
        before=_source(fn,x,y,cap,alt,target_op='+',decoy_op='+',shape=shape)
        wrap={'operands_abs':'abs','operands_neg':'neg'}[kind]
        after=_source(fn,x,y,cap,alt,target_op='+',decoy_op='+',wrap=wrap,shape=shape)
    elif kind.startswith('cmp_'):
        before=_source(fn,x,y,cap,alt,target_op='-',decoy_op='-',cmp='<',shape=shape)
        cmp={'cmp_lte':'<=','cmp_gt':'>','cmp_gte':'>=','cmp_eq':'=='}[kind]
        after=_source(fn,x,y,cap,alt,target_op='-',decoy_op='-',cmp=cmp,shape=shape)
    else: raise ValueError(kind)
    return before,after


def grouped_training_demos():
    kinds=('binop_add','binop_mult','binop_floordiv','binop_mod','operands_abs','operands_neg','cmp_lte','cmp_gt','cmp_gte','cmp_eq')
    return {kind:(_demo(kind,0,'direct'),_demo(kind,1,'alias')) for kind in kinds}


def learn_r249_library():
    lib=learn_relational_context_library(grouped_training_demos())
    if len(lib)!=10 or any(m.support!=2 for m in lib): raise AssertionError((len(lib),[m.support for m in lib]))
    return lib


def _opaque(seed,role): return 'g_'+hashlib.sha256(f'r249|{seed}|{role}'.encode()).hexdigest()[:10]


def _episode(seed):
    fn='f_'+hashlib.sha256(f'r249|{seed}|fn'.encode()).hexdigest()[:12]
    x,y,cap,alt=(_opaque(seed,r) for r in ('x','y','cap','alt'))
    shape='deep' if seed%2 else 'nested'
    source=_source(fn,x,y,cap,alt,target_op='-',decoy_op='-',cmp='<',shape=shape)
    lib=learn_r249_library(); essential=[]
    for m in lib:
        b=m.base
        if b.slot=='binop' and b.src=='Sub' and b.dst=='Add': essential.append(m)
        elif b.slot=='operand_wrapper' and b.dst=='abs': essential.append(m)
        elif b.slot=='compare' and b.src=='Lt' and b.dst=='LtE': essential.append(m)
    if len(essential)!=3: raise AssertionError('essential relational macros')
    target=apply_relational_context_macros(source,essential)
    return source,target,tuple(sorted(m.macro_id for m in essential)),essential


def _r248_baseline_macros():
    # Train the old fixed guarded_return_value context on direct demos only.
    demos=[]
    for kind in ('binop_add','operands_abs','cmp_lte'):
        demos.append(_demo(kind,0,'direct'))
    return learn_contextual_patch_library(tuple(demos))


def _compile(source):
    ns={'__builtins__':{'abs':abs,'max':max}}
    exec(compile(source,'<r249>','exec'),ns,ns)
    fns=[v for k,v in ns.items() if k.startswith('f_')]
    if len(fns)!=1: raise AssertionError('compile')
    return fns[0]


def _tests(seed,target):
    fn=_compile(target); out=[]
    for i,args in enumerate(itertools.product(range(-3,4),range(-3,4),range(0,7),range(-3,4))):
        out.append(PatchTest(f't:{seed}:{i:04d}',tuple(args),fn(*args)))
    return tuple(out)


def _order(seed,tests): return tuple(sorted((t.test_id for t in tests),key=lambda tid:hashlib.sha256(f'r249-order|{seed}|{tid}'.encode()).hexdigest()))

def _passes_all(source,tests):
    try: fn=_compile(source)
    except Exception: return False
    return all(fn(*t.args)==t.expected for t in tests)


def run_heldout_episode(seed):
    if seed not in HELDOUT_EPISODES: raise ValueError(seed)
    source,target,essential_ids,_essential=_episode(seed); lib=learn_r249_library(); candidates=enumerate_relational_candidates(source,lib)
    tests=_tests(seed,target); order=_order(seed,tests)
    receipt=solve_patch_with_sparse_tests(candidates,tests,initial_test_ids=order[:4],hidden_order=order,max_counterexamples=24)
    old=apply_contextual_patch_macros(source,_r248_baseline_macros())
    selected=() if receipt.candidate is None else receipt.candidate.macro_ids
    return {
      'seed':seed,'exact':receipt.exact,'status':receipt.status,'learned_macros':len(lib),'initial_candidates':receipt.initial_candidate_count,
      'selected_exact_macro_set':set(selected)==set(essential_ids),'r248_fixed_context_baseline_exact':_passes_all(old,tests),
      'required_feature_sets':[list(m.required_features) for m in lib],
      'initial_tests':receipt.initial_tests,'counterexamples_revealed':receipt.counterexamples_revealed,'observed_tests':len(receipt.observed_test_ids),
      'feedback_fraction':receipt.feedback_fraction,'candidate_test_evaluations':receipt.candidate_test_evaluations,'exhaustive_tests_verified':receipt.exhaustive_tests_verified,
      'test_suite_size':len(tests),'opaque_identifiers':all(tok not in source for tok in ('left','right','limit','train_')),
    }


def run_frozen_heldout():
    rows=[run_heldout_episode(s) for s in HELDOUT_EPISODES]
    summary={
      'episodes':6,'exact':sum(r['exact'] for r in rows),'false_accepts':sum(not r['exact'] for r in rows),'learned_macros':rows[0]['learned_macros'],
      'initial_candidates':rows[0]['initial_candidates'],'selected_exact_macro_set':sum(r['selected_exact_macro_set'] for r in rows),
      'r248_fixed_context_baseline_exact':sum(r['r248_fixed_context_baseline_exact'] for r in rows),'initial_tests_per_episode':4,
      'max_counterexamples_revealed':max(r['counterexamples_revealed'] for r in rows),'max_observed_tests':max(r['observed_tests'] for r in rows),
      'max_feedback_fraction':max(r['feedback_fraction'] for r in rows),'mean_feedback_fraction':sum(r['feedback_fraction'] for r in rows)/6,
      'max_candidate_test_evaluations':max(r['candidate_test_evaluations'] for r in rows),'exhaustive_tests_per_episode':min(r['exhaustive_tests_verified'] for r in rows),
      'test_suite_size':rows[0]['test_suite_size'],'opaque_identifiers':all(r['opaque_identifiers'] for r in rows),
      'learned_predicate_features':sorted({f for r in rows for fs in r['required_feature_sets'] for f in fs}),
      'execution_mode':'learned relational program-graph context predicates + compiled Python patches + executable tests'
    }
    gates={'all_exact':summary['exact']==6,'zero_false_accepts':summary['false_accepts']==0,'learned_distractor_library':summary['learned_macros']==10,
      'selected_exact_all':summary['selected_exact_macro_set']==6,'r248_fixed_baseline_fails_all':summary['r248_fixed_context_baseline_exact']==0,
      'sparse_feedback_under_1_percent':summary['max_feedback_fraction']<=0.01,'final_exhaustive_execution':summary['exhaustive_tests_per_episode']==2401,
      'opaque_identifiers':summary['opaque_identifiers'],'predicate_features_learned':len(summary['learned_predicate_features'])>=1}
    return {'schema_version':1,'milestone':'R2.49 Relational Context Predicate Induction','heldout_episodes':list(HELDOUT_EPISODES),'rows':rows,'summary':summary,'gates':gates,'all_gates_pass':all(gates.values())}
