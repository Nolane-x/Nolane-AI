from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_meta_learning_kernel import MetaLearningConfig, PublicTaskSignature
from cogcoder.r269_transfer_runtime import _filter, _scratch_hypotheses, _structural_key


def inspect(names, target, diagnostics, cap):
    sig = PublicTaskSignature(
        role_names=tuple(names), numeric_domain='finite_numeric',
        allowed_binary_ops=('add','sub','mul','min','max'), query_space_digest='debug',
        budget_contract=f'candidate<={cap}',
    )
    cfg = MetaLearningConfig(max_diagnostic_queries=len(diagnostics), transfer_candidate_cap=96,
                             scratch_candidate_cap=cap, scratch_max_depth=2, min_scratch_partitions=2)
    rows = _scratch_hypotheses(sig, cfg)
    key = _structural_key(target)
    print('roles', len(names), 'cap', cap, 'rows', len(rows), 'target_present', any(_structural_key(r.expression) == key for r in rows))
    live = list(rows)
    for index, context in enumerate(diagnostics):
        if len(live) <= 1:
            break
        observed = eval_target(target, context)
        live = _filter(live, context, observed)
        print(' after', index + 1, 'live', len(live), 'min_cost', min((r.expression.cost for r in live), default=None), 'costs', sorted({r.expression.cost for r in live})[:8])
    print(' final target survivors', sum(_structural_key(r.expression) == key for r in live))
    for row in live[:12]:
        print('  ', row.expression.cost, _structural_key(row.expression))


def eval_target(expr, context):
    from cogcoder.r256_operator_dsl import evaluate_expr
    return evaluate_expr(expr, context)


x, y = Field('x'), Field('y')
inspect(
    ('x','y'), Binary('sub', x, y),
    ({'x':0,'y':1},{'x':1,'y':0},{'x':2,'y':3},{'x':-2,'y':4},{'x':5,'y':-1},{'x':3,'y':7}),
    220,
)

a,b,c,d = map(Field, ('a','b','c','d'))
inspect(
    ('a','b','c','d'), Binary('sub', Binary('add',a,b), Binary('add',c,d)),
    (
        {'a':1,'b':2,'c':5,'d':1},{'a':2,'b':7,'c':3,'d':4},{'a':-3,'b':5,'c':2,'d':8},
        {'a':9,'b':-2,'c':4,'d':1},{'a':6,'b':3,'c':-5,'d':2},{'a':11,'b':4,'c':7,'d':-3},
        {'a':-8,'b':9,'c':6,'d':5},{'a':13,'b':-7,'c':2,'d':10},
    ),
    8192,
)
