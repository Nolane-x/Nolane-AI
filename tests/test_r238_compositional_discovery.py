from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_language_synthesis import synthesize_operator_proposals
from cogcoder.r237_query_generation import GeneratedQuery
from cogcoder.r238_compositional_discovery import discover_with_compositional_probes
from cogcoder.r238_probe_language import probe_prediction_row


def _fixture():
    proposals = synthesize_operator_proposals(2, max_nodes=1, primitive_budget=4)[:3]
    ids = [p.operator_id for p in proposals]
    q0 = GeneratedQuery.create((0, 0), (0, 0))
    q1 = GeneratedQuery.create((0, 0), (0, 1))
    q2 = GeneratedQuery.create((0, 0), (1, 0))
    predictions = {
        q0.query_id: {ids[0]: True, ids[1]: True, ids[2]: True},
        q1.query_id: {ids[0]: True, ids[1]: True, ids[2]: False},
        q2.query_id: {ids[0]: True, ids[1]: False, ids[2]: True},
    }
    return proposals, (q0, q1, q2), (q0,), predictions, ids[0]


def _verifier(target, predictions):
    def verify(probe):
        label = probe_prediction_row(probe, predictions)[target]
        return VerifierObservation(probe.probe_id, label, .999)
    return verify


def test_compositional_probe_can_resolve_with_same_budget_when_atomic_cannot():
    proposals, universe, pool, predictions, target = _fixture()
    kwargs = dict(
        proposals=proposals, universe=universe, initial_pool=pool, atom_predictions=predictions,
        verifier=_verifier(target, predictions), counterexample_check=lambda p: p.operator_id == target,
        query_budget=2, accept_probability=.9, accept_margin=.7, max_mdl_cost=1, complexity_weight=0.0,
        atom_shortlist_size=2,
    )
    comp = discover_with_compositional_probes(**kwargs, mode='compositional')
    atom = discover_with_compositional_probes(**kwargs, mode='atomic_only')
    pool_only = discover_with_compositional_probes(**kwargs, mode='pool_only')
    assert comp.status == 'accept' and comp.operator_id == target
    assert atom.status == 'abstain'
    assert pool_only.status == 'abstain'
    assert len(comp.queries) == 2
    assert len(atom.queries) == 2
    assert len(comp.composite_probe_ids) == 1
    assert comp.synthesis_candidates_evaluated > 0


def test_counterexample_authority_remains_fail_closed():
    proposals, universe, pool, predictions, target = _fixture()
    decision = discover_with_compositional_probes(
        proposals, universe, pool, predictions,
        verifier=_verifier(target, predictions), counterexample_check=lambda p: False,
        query_budget=2, accept_probability=.9, accept_margin=.7, max_mdl_cost=1,
        complexity_weight=0.0, atom_shortlist_size=2, mode='compositional',
    )
    assert decision.status == 'abstain'
    assert decision.operator_id is None
    assert decision.reason == 'counterexample_rejected_top_operator'


def test_modes_share_one_total_verifier_call_budget():
    proposals, universe, pool, predictions, target = _fixture()
    for mode in ('compositional', 'atomic_only', 'pool_only'):
        decision = discover_with_compositional_probes(
            proposals, universe, pool, predictions,
            verifier=_verifier(target, predictions), counterexample_check=lambda p: p.operator_id == target,
            query_budget=2, accept_probability=.999999, accept_margin=.999999,
            max_mdl_cost=1, complexity_weight=0.0, atom_shortlist_size=2, mode=mode,
        )
        assert len(decision.queries) <= 2
