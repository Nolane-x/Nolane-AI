from cogcoder.r18_active_gate import decide_active_train_gate

def test_active_gate_accepts_only_recurrent_causal_gain_and_family_preservation():
    full={'solved':30,'families':{'a':8,'b':7,'c':7,'d':8}};reset={'solved':24,'families':{'a':7,'b':6,'c':5,'d':6}};random=[{'solved':5},{'solved':7},{'solved':6},{'solved':4},{'solved':8}];v=decide_active_train_gate(full,reset,random);assert v['accepted'] is True and v['random_mean_solved']==6.0 and v['recurrent_gain_over_reset']==6
def test_active_gate_rejects_if_gain_below_five_or_any_family_regresses():
    reset={'solved':24,'families':{'a':7,'b':6,'c':5,'d':6}};random=[{'solved':5} for _ in range(5)];low={'solved':28,'families':{'a':8,'b':7,'c':6,'d':7}};assert decide_active_train_gate(low,reset,random)['accepted'] is False;regress={'solved':32,'families':{'a':6,'b':9,'c':8,'d':9}};assert decide_active_train_gate(regress,reset,random)['accepted'] is False
