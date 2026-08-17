from cogcoder.r248_contextual_patch import infer_contextual_patch_macro, learn_contextual_patch_library, apply_contextual_patch_macros


def src(fn='f', x='x', y='y', cap='cap', alt='alt'):
    return f'''def {fn}({x}, {y}, {cap}, {alt}):
    shadow = {x} - {y}
    if shadow < {alt}:
        penalty = 1
    else:
        penalty = 2
    total = {x} - {y}
    if total < {cap}:
        return total + penalty
    return {cap} + 1 + shadow + penalty
'''


def test_context_inference_abstracts_identifier_names_and_localizes_binop():
    a = src()
    b = a.replace('total = x - y', 'total = x + y')
    c = src('g','left','right','limit','other')
    d = c.replace('total = left - right', 'total = left + right')
    ma = infer_contextual_patch_macro(a,b)
    mb = infer_contextual_patch_macro(c,d)
    assert ma.signature == mb.signature
    assert ma.macro_id == mb.macro_id
    assert ma.context_role == 'guarded_return_value'


def test_contextual_application_changes_main_site_but_not_decoy_site():
    before = src()
    macro = infer_contextual_patch_macro(before, before.replace('total = x - y', 'total = x + y'))
    patched = apply_contextual_patch_macros(before, (macro,))
    assert 'shadow = x - y' in patched
    assert 'total = x + y' in patched


def test_support_accumulates_across_renamed_contextual_demos():
    a=src(); b=a.replace('if total < cap:', 'if total <= cap:')
    c=src('g','l','r','limit','alt2'); d=c.replace('if total < limit:', 'if total <= limit:')
    lib=learn_contextual_patch_library(((a,b),(c,d)))
    assert len(lib)==1 and lib[0].support==2
