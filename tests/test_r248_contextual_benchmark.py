from benchmarks.kfigg.r248_contextual_multisite_transfer import HELDOUT_EPISODES,learn_r248_library,run_frozen_heldout,run_heldout_episode

def test_library_learns_contextual_distractors_from_renamed_demos():
    lib=learn_r248_library()
    assert len(lib)==10 and all(m.support==2 for m in lib)
    assert {m.slot for m in lib}=={'binop','operand_wrapper','compare'}
    assert {m.context_role for m in lib}=={'guarded_return_value'}

def test_contextual_multisite_transfer_beats_global_application_baseline():
    r=run_frozen_heldout(); assert r['all_gates_pass'],r
    s=r['summary']
    assert s['exact']==6 and s['false_accepts']==0
    assert s['selected_exact_macro_set']==6
    assert s['global_r247_baseline_exact']==0
    assert s['max_feedback_fraction']<=0.02
    assert s['exhaustive_tests_per_episode']==2401

def test_opaque_renames_preserve_same_contextual_patch_set():
    a=run_heldout_episode(HELDOUT_EPISODES[0]); b=run_heldout_episode(HELDOUT_EPISODES[-1])
    assert a['exact'] and b['exact'] and a['selected_exact_macro_set'] and b['selected_exact_macro_set']
