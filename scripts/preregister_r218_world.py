#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

from nolane_world.v5.runtime import LivingWorldV5

ROOT = Path('/mnt/data/nolane_r218_world_v5')
OUT = Path('research/R2_18_WORLD_PREREGISTRATION.json')

PREDICTIONS = {
    'r218-p1-external-transfer': (
        'A mechanism-level periodic guarded-recurrence skill established on the synthetic source family will, without changing the generic verifier, uniquely retain the NIST FIPS 197 AES-128 Appendix A.1 target against the frozen hard-decoy cohort.'
    ),
    'r218-p2-local-quarantine': (
        'A correctness-regressing or false-accepting transfer in an incompatible domain will quarantine only that domain while preserving an independently validated source-domain route for the same skill.'
    ),
    'r218-p3-dedup-capacity': (
        'Two skills with identical kind, mechanism tags, and behavior digest will merge provenance without increasing governed library capacity.'
    ),
    'r218-p4-rollback': (
        'After a capacity/governance update, rollback will create a new audit version whose routable records exactly equal the selected prior snapshot rather than mutating history in place.'
    ),
}

ENGINE_PREDICTION = {
    'problem-formulation': 'r218-p4-rollback',
    'representation-shift': 'r218-p3-dedup-capacity',
    'hypothesis-ecology': 'r218-p1-external-transfer',
    'unknown-hunter': 'r218-p2-local-quarantine',
}


def payload_for(engine: str) -> dict:
    mechanics = {
        'problem-formulation': (
            'Mutable library state can hide regressions and make recovery unverifiable.',
            'An immutable version graph makes rollback identity testable.',
            'Replace in-place rollback with a new version pointing to an exact prior record snapshot.',
        ),
        'representation-shift': (
            'Domain labels fragment reusable capabilities even when behavior is identical.',
            'Mechanism-plus-behavior identity exposes true duplicates across domains.',
            'Canonicalize skill identity by kind, mechanism tags and behavior digest while merging lineage separately.',
        ),
        'hypothesis-ecology': (
            'A periodic guarded-recurrence verifier may encode a reusable structural mechanism rather than an AES-specific answer.',
            'If mechanism-level, source validation should transfer to AES under a domain adapter and reject hard core-rule decoys.',
            'Hold the generic verifier fixed and change only the recurrence adapter between synthetic source and NIST AES.',
        ),
        'unknown-hunter': (
            'Cross-domain reuse can create negative transfer even when mechanism tags overlap.',
            'Domain-local evidence states can contain damage without deleting globally useful skills.',
            'Inject a correctness-regressing transfer observation in one domain and compare routing in that domain versus source.',
        ),
        'research-agenda': (
            'Cross-domain transfer, negative-transfer isolation, deduplication, bounded capacity and rollback are separable failure modes.',
            'A preregistered gate matrix prevents one success from masking another failure.',
            'Freeze predictions and evaluate each gate independently before aggregating readiness credit.',
        ),
        'causal-model': (
            'Transfer quality depends on mechanism match plus evidence governance, not domain-name similarity alone.',
            'Mechanism matching proposes trials; evidence promotion/quarantine and capacity policy determine durable routing.',
            'Intervene separately on mechanism overlap, evidence outcome and capacity budget to identify their effects.',
        ),
    }
    cause, effect, intervention = mechanics[engine]
    payload = {
        'claim': cause,
        'new_information_or_prediction': effect,
        'falsifier_or_risk': 'Reject the mechanism if the frozen test can pass when the named causal gate is removed or if an unrelated domain label controls the result.',
        'provenance_or_lineage': 'Nolane-AI:R2.17@01d162a49a332dc4aa9bd0cff670fa4c9cc09884 + NIST:FIPS-197-upd1',
        'mechanism': {'cause': cause, 'effect': effect, 'intervention': intervention},
    }
    pid = ENGINE_PREDICTION.get(engine)
    if pid:
        payload['prediction_id'] = pid
        payload['new_information_or_prediction'] = PREDICTIONS[pid]
    return payload


def main() -> int:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    runtime = LivingWorldV5(ROOT)
    model = runtime.register_worker('r218-research-model', 'model')
    verifier = runtime.register_worker('r218-evidence-verifier', 'verifier')
    entered = runtime.enter(
        'Determine whether R2.18 can add safe mechanism-level cross-domain skill transfer and open-ended library governance without changing R2.17 sealed decision logic or adding neural parameters.',
        depth='W4',
        domain='software-research',
        constraints=[
            'R2.17 accepted decision logic is immutable.',
            'No held-out execution before durable prediction registration.',
            'External oracle validates fixture provenance but is not a candidate-filter predicate.',
            'Readiness credit requires falsifiable execution evidence.',
        ],
        anti_goals=[
            'Do not claim AGI or broad frontier parity.',
            'Do not convert documentation-only changes into readiness credit.',
        ],
    )
    wid = entered['world_id']
    evidence = [
        runtime.record_evidence(
            wid,
            verifier.principal_id,
            credential=verifier.credential,
            evidence_id='r218-parent-r217',
            lineage='github:Nolane-x/Nolane-AI:01d162a49a332dc4aa9bd0cff670fa4c9cc09884',
            content={
                'milestone': 'R2.17 Hierarchical Library-Growing CEGIS',
                'agi_engineering_readiness_after': 21.7,
                'next_bottleneck': 'cross-domain concept transfer with open-ended library governance',
            },
            subjects=['r218-parent', 'readiness-baseline'],
        ),
        runtime.record_evidence(
            wid,
            verifier.principal_id,
            credential=verifier.credential,
            evidence_id='r218-nist-fips197-upd1',
            lineage='nist:FIPS-197-upd1:2023-05-09',
            content={
                'publication': 'FIPS 197-upd1 Advanced Encryption Standard (AES)',
                'updated': '2023-05-09',
                'note': 'NIST states the 2023 update makes no technical changes to the algorithm and includes key-schedule diagrams.',
                'doi': '10.6028/NIST.FIPS.197-upd1',
            },
            subjects=['external-aes-standard', 'r218-fixture-provenance'],
        ),
    ]

    submissions = []
    completed_engines: set[str] = set()
    while not {'research-agenda', 'causal-model'} <= completed_engines:
        task = runtime.next_task(wid, model.principal_id, credential=model.credential)
        engine = task['engine']
        if engine == 'discriminating-experiment':
            raise RuntimeError('experiment became ready before preregistration phase was deliberately closed')
        payload = payload_for(engine)
        result = runtime.submit(wid, task['task_id'], model.principal_id, payload, credential=model.credential)
        submissions.append({'engine': engine, 'instruction_id': task['instruction_id'], 'result': result, 'prediction_id': payload.get('prediction_id')})
        if not result.get('accepted'):
            raise RuntimeError(f'World rejected {engine}: {result}')
        completed_engines.add(engine)

    events = runtime.store.events(wid)
    prediction_events = [
        {'seq': e['seq'], 'event_type': e['event_type'], 'event': e['event'], 'hash': e['hash'], 'prev_hash': e['prev_hash']}
        for e in events
        if e['event_type'] == 'prediction.registered'
    ]
    registered = {e['event']['prediction_id'] for e in prediction_events}
    missing = set(PREDICTIONS) - registered
    if missing:
        raise RuntimeError(f'missing prediction registrations: {sorted(missing)}')
    if any(e['event_type'] in {'experiment', 'experiment.completed'} for e in events):
        raise RuntimeError('experiment event present during preregistration phase')

    checkpoint = runtime.store.checkpoint(wid)
    audit = runtime.store.audit(wid)
    context = runtime.context(wid)
    output = {
        'schema_version': 1,
        'milestone': 'R2.18 Cross-Domain Transfer + Open-Ended Library Governance',
        'phase': 'pre-heldout-preregistration',
        'world_id': wid,
        'world_depth': entered['depth'],
        'program_signature': entered['program_signature'],
        'worker_principals': {
            'model': model.principal_id,
            'verifier': verifier.principal_id,
        },
        'trusted_evidence': evidence,
        'predictions': PREDICTIONS,
        'prediction_events': prediction_events,
        'submissions': submissions,
        'frontier_after_preregistration': context['vm_frontier'],
        'audit': audit,
        'checkpoint': {
            'checkpoint_id': checkpoint['checkpoint_id'],
            'version': checkpoint['version'],
            'digest': checkpoint['digest'],
            'verified': runtime.store.verify_checkpoint(checkpoint),
        },
        'heldout_executed': False,
        'constitution_note': 'All four predictions were durably registered before any discriminating-experiment task was issued or executed.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'world_id': wid,
        'audit': audit,
        'registered_predictions': sorted(registered),
        'frontier': context['vm_frontier'],
        'checkpoint_verified': output['checkpoint']['verified'],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
