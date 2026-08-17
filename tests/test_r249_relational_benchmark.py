from benchmarks.kfigg.r249_relational_context_transfer import HELDOUT_EPISODES,learn_r249_library,run_frozen_heldout,run_heldout_episode

def test_library_learns_relational_predicates_across_direct_and_alias_demos():
    lib=learn_r249_library(); assert len(lib)==10 and all(m.support==2 for m in lib)
    assert all(m.required_features for m in lib)

def test_relational_context_transfer_beats_r248_fixed_context_under_graph_reshaping():
    r=run_frozen_heldout(); assert r['all_gates_pass'],r
    s=r['summary']; assert s['exact']==6 and s['false_accepts']==0
    assert s['selected_exact_macro_set']==6 and s['r248_fixed_context_baseline_exact']==0
    assert s['exhaustive_tests_per_episode']==2401 and s['max_feedback_fraction']<=0.01

def test_opaque_nested_and_deep_alias_worlds_keep_same_learned_patch_behavior():
    a=run_heldout_episode(HELDOUT_EPISODES[0]); b=run_heldout_episode(HELDOUT_EPISODES[-1])
    assert a['exact'] and b['exact'] and a['selected_exact_macro_set'] and b['selected_exact_macro_set']
