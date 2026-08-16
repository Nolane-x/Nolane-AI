from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_language_synthesis import OperatorProposal
from cogcoder.r220_operator_language import OperatorProgram, canonical_operator_id
from cogcoder.r221_adaptive_evidence import discover_operator_adaptive


def _proposal(program, mdl):
    return OperatorProposal(program, canonical_operator_id(program, 2), mdl)


def test_adaptive_accepts_early_before_max_budget():
    a = _proposal(OperatorProgram.identity(), 1); b = _proposal(OperatorProgram.xor_mask((1, 0)), 1); proposals = (a, b)
    predictions = {'q1': {a.operator_id: True, b.operator_id: False}, 'q2': {a.operator_id: True, b.operator_id: False}, 'q3': {a.operator_id: True, b.operator_id: False}, 'q4': {a.operator_id: True, b.operator_id: False}}
    decision = discover_operator_adaptive(proposals, tuple(predictions), predictions, verifier=lambda q: VerifierObservation(q, True, .99), counterexample_check=lambda p: p.operator_id == a.operator_id, base_budget=2, max_budget=4, accept_probability=.90, accept_margin=.75, max_mdl_cost=3, complexity_weight=0.0, continuation_min_disagreement=.01, recoverability_floor=.01)
    assert decision.status == 'accept' and decision.operator_id == a.operator_id and len(decision.queries) < 4 and decision.stop_reason == 'accepted'


def test_adaptive_extends_beyond_base_when_uncertainty_remains_recoverable():
    a = _proposal(OperatorProgram.identity(), 1); b = _proposal(OperatorProgram.xor_mask((1, 0)), 1); c = _proposal(OperatorProgram.xor_mask((0, 1)), 1); proposals = (a, b, c)
    predictions = {'q1': {a.operator_id: True,b.operator_id: False,c.operator_id: True},'q2': {a.operator_id: True,b.operator_id: True,c.operator_id: False},'q3': {a.operator_id: False,b.operator_id: True,c.operator_id: False},'q4': {a.operator_id: True,b.operator_id: False,c.operator_id: False},'q5': {a.operator_id: True,b.operator_id: False,c.operator_id: False}}
    truth={'q1':True,'q2':True,'q3':False,'q4':True,'q5':True}
    def verifier(q): return VerifierObservation(q, False, .56) if q == 'q1' else VerifierObservation(q, truth[q], .99)
    decision=discover_operator_adaptive(proposals,tuple(predictions),predictions,verifier=verifier,counterexample_check=lambda p:p.operator_id==a.operator_id,base_budget=2,max_budget=5,accept_probability=.90,accept_margin=.70,max_mdl_cost=3,complexity_weight=0.0,continuation_min_disagreement=.01,recoverability_floor=.01)
    assert decision.status=='accept' and decision.operator_id==a.operator_id and len(decision.queries)>2 and decision.extended is True


def test_adaptive_abstains_when_remaining_queries_have_no_value_of_information():
    a=_proposal(OperatorProgram.identity(),1); b=_proposal(OperatorProgram.xor_mask((1,0)),1)
    predictions={'q1':{a.operator_id:True,b.operator_id:True},'q2':{a.operator_id:False,b.operator_id:False},'q3':{a.operator_id:True,b.operator_id:True}}
    decision=discover_operator_adaptive((a,b),tuple(predictions),predictions,verifier=lambda q:VerifierObservation(q,predictions[q][a.operator_id],.99),counterexample_check=lambda p:True,base_budget=1,max_budget=3,accept_probability=.90,accept_margin=.50,max_mdl_cost=3,complexity_weight=0.0,continuation_min_disagreement=.01,recoverability_floor=.01)
    assert decision.status=='abstain' and len(decision.queries)<=1 and decision.stop_reason=='low_value_of_information'


def test_adaptive_never_exceeds_hard_max_budget():
    a=_proposal(OperatorProgram.identity(),1); b=_proposal(OperatorProgram.xor_mask((1,0)),1)
    predictions={f'q{i}':{a.operator_id:bool(i%2),b.operator_id:not bool(i%2)} for i in range(10)}
    decision=discover_operator_adaptive((a,b),tuple(predictions),predictions,verifier=lambda q:VerifierObservation(q,True,.5001),counterexample_check=lambda p:False,base_budget=2,max_budget=4,accept_probability=.99,accept_margin=.99,max_mdl_cost=3,complexity_weight=0.0,continuation_min_disagreement=.0,recoverability_floor=.0)
    assert decision.status=='abstain' and len(decision.queries)==4 and decision.stop_reason=='max_budget_exhausted'
