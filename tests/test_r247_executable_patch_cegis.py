from cogcoder.r247_executable_patch_cegis import (
    apply_patch_macros,
    enumerate_patch_candidates,
    infer_patch_macro,
    learn_patch_library,
)


def test_infer_binop_rewrite_abstracts_variable_names():
    a = infer_patch_macro('def f(x,y):\n    return x-y\n', 'def f(x,y):\n    return x+y\n')
    b = infer_patch_macro('def g(left,right):\n    return left-right\n', 'def g(left,right):\n    return left+right\n')
    assert a.signature == b.signature == ('binop', 'replace', 'Sub', 'Add')
    assert a.macro_id == b.macro_id


def test_infer_operand_wrapper_and_compare_rewrite():
    wrap = infer_patch_macro('def f(x,y):\n    return x+y\n', 'def f(x,y):\n    return abs(x)+abs(y)\n')
    cmp = infer_patch_macro(
        'def f(x,cap):\n    if x < cap:\n        return x\n    return cap\n',
        'def f(x,cap):\n    if x <= cap:\n        return x\n    return cap\n',
    )
    assert wrap.signature == ('operand_wrapper', 'wrap', None, 'abs')
    assert cmp.signature == ('compare', 'replace', 'Lt', 'LtE')


def test_learned_support_accumulates_across_renamed_demos():
    demos = (
        ('def f(x,y):\n    return x-y\n', 'def f(x,y):\n    return x+y\n'),
        ('def g(a,b):\n    return a-b\n', 'def g(a,b):\n    return a+b\n'),
    )
    library = learn_patch_library(demos)
    assert len(library) == 1
    assert library[0].support == 2


def test_candidate_enumerator_semantically_dedupes_noop_macro_choices():
    source = 'def f(x,y):\n    return x-y\n'
    macros = learn_patch_library((
        (source, 'def f(x,y):\n    return x+y\n'),
        ('def c(x,cap):\n    if x < cap:\n        return x\n    return cap\n',
         'def c(x,cap):\n    if x <= cap:\n        return x\n    return cap\n'),
    ))
    candidates = enumerate_patch_candidates(source, macros)
    assert len(candidates) == 2
    assert candidates[0].edit_count == 0
    assert candidates[1].edit_count == 1
