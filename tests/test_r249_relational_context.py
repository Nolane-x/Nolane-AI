from benchmarks.kfigg.r249_relational_context_transfer import _demo
from cogcoder.r249_relational_context import learn_relational_context_macro, relational_features_for_site, _candidate_nodes
from cogcoder.r247_executable_patch_cegis import _parse_function, infer_patch_macro


def test_learns_context_predicate_from_positive_and_unchanged_sites():
    m=learn_relational_context_macro((_demo('binop_add',0,'direct'),_demo('binop_add',1,'alias')))
    assert m.support==2 and m.positive_sites==2 and m.negative_sites>=2
    assert m.required_features
    assert all(not f.startswith('name:') for f in m.required_features)


def test_learned_predicate_matches_positive_alias_site_not_decoy():
    before,after=_demo('binop_add',1,'alias'); base=infer_patch_macro(before,after); fn=_parse_function(before)
    nodes=_candidate_nodes(fn,base); matched=[n for n in nodes if set(learn_relational_context_macro((_demo('binop_add',0,'direct'),(before,after))).required_features).issubset(relational_features_for_site(fn,n))]
    assert len(matched)==1
