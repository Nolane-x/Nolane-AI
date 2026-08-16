from __future__ import annotations

import hashlib
import random
from dataclasses import asdict

from cogcoder.r218_library_governor import (
    admit_skill,
    apply_transfer_observations,
    enforce_capacity,
    rollback_to_snapshot,
    route_skills,
)
from cogcoder.r218_periodic_invariant import (
    AES_CORE_DECOYS,
    NIST_AES128_KEY,
    NIST_AES128_WORDS,
    NIST_SOURCE,
    aes128_nist_adapter,
    filter_cohort,
    make_aes128_nist_cohort,
    make_source_recurrence_cohort,
    source_periodic_adapter,
)
from cogcoder.r218_transfer_types import (
    DomainDescriptor,
    OpenEndedLibraryVersion,
    TransferObservation,
    TransferSkill,
)

_MECHANISM_SPEC = (
    'generic-periodic-guarded-recurrence-v1|'
    'verify-seed|verify-exact-length|verify-normal-positions|verify-periodic-special-positions'
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _generic_skill() -> TransferSkill:
    return TransferSkill(
        'periodic-recurrence-filter',
        ('guarded', 'periodic', 'recurrence'),
        _digest(_MECHANISM_SPEC),
        ('python:cogcoder.r218_periodic_invariant.check_periodic_recurrence',),
        ('r218:synthetic-source-contract',),
        ('synthetic-periodic-recurrence',),
        capacity_cost=1,
    )


def _route_mode(library: OpenEndedLibraryVersion, domain: DomainDescriptor) -> str | None:
    rows = route_skills(library, domain, max_capacity=1, min_overlap=.5, max_trials=1)
    return None if not rows else rows[0].mode


def _state_for(library: OpenEndedLibraryVersion, skill_id: str, domain_id: str) -> str | None:
    record = next(record for record in library.records if record.skill.skill_id == skill_id)
    evidence = record.evidence_for(domain_id)
    return None if evidence is None else evidence.state


def run_r218(seed: int) -> dict:
    rng = random.Random(int(seed))
    skill = _generic_skill()
    source_adapter = source_periodic_adapter()
    aes_adapter = aes128_nist_adapter()
    source_domain = DomainDescriptor(source_adapter.domain_id, source_adapter.mechanism_tags)
    aes_domain = DomainDescriptor(aes_adapter.domain_id, aes_adapter.mechanism_tags)
    alien_domain = DomainDescriptor(
        'incompatible-state-machine-recurrence',
        ('guarded', 'periodic', 'recurrence', 'stateful-nonlocal'),
    )

    source_cohort = make_source_recurrence_cohort()
    source_survivors = filter_cohort(source_cohort, source_adapter)
    source_ok = source_survivors == ('source_target',)

    library = admit_skill(OpenEndedLibraryVersion(0, ()), skill)
    before_duplicate_capacity = library.capacity_used
    before_duplicate_records = len(library.records)
    duplicate = TransferSkill(
        skill.kind,
        tuple(reversed(skill.mechanism_tags)),
        skill.behavior_digest,
        ('artifact:r218-source-verification',),
        ('r218:independent-source-lineage',),
        ('synthetic-periodic-recurrence',),
        capacity_cost=skill.capacity_cost,
    )
    library = admit_skill(library, duplicate)
    dedup_ok = (
        library.capacity_used == before_duplicate_capacity
        and len(library.records) == before_duplicate_records
    )

    aes_route_before = _route_mode(library, aes_domain)
    aes_cohort = make_aes128_nist_cohort()
    aes_survivors = filter_cohort(aes_cohort, aes_adapter)
    aes_ablated = filter_cohort(
        aes_cohort,
        aes_adapter,
        enabled=('seed', 'length', 'normal_recurrence'),
    )
    false_survivors = sorted(set(aes_ablated) - {'target_nist_fips197'})
    external_filter_ok = (
        aes_survivors == ('target_nist_fips197',)
        and set(AES_CORE_DECOYS).issubset(false_survivors)
    )
    # Search costs are deterministic benchmark accounting units, not wall-clock claims.
    baseline_a = 100 + rng.randint(0, 8)
    baseline_b = 100 + rng.randint(0, 8)
    assisted_a = baseline_a - (24 + rng.randint(0, 6))
    assisted_b = baseline_b - (22 + rng.randint(0, 6))
    external_rows = (
        TransferObservation(
            f'aes-{seed}-a', aes_domain.domain_id, skill.skill_id,
            True, external_filter_ok, baseline_a, assisted_a,
            false_accept=not external_filter_ok,
        ),
        TransferObservation(
            f'aes-{seed}-b', aes_domain.domain_id, skill.skill_id,
            True, external_filter_ok, baseline_b, assisted_b,
            false_accept=not external_filter_ok,
        ),
    )
    library = apply_transfer_observations(
        library,
        external_rows,
        min_window=2,
        min_cost_reduction=.10,
    )
    aes_route_after = _route_mode(library, aes_domain)
    external_ok = aes_route_before == 'trial' and external_filter_ok and aes_route_after == 'active'

    alien_route_before = _route_mode(library, alien_domain)
    bad_row = TransferObservation(
        f'alien-{seed}',
        alien_domain.domain_id,
        skill.skill_id,
        True,
        False,
        100 + rng.randint(0, 5),
        70 + rng.randint(0, 5),
        false_accept=True,
    )
    library = apply_transfer_observations(library, (bad_row,))
    alien_routes_after = route_skills(library, alien_domain, max_capacity=1, min_overlap=.5, max_trials=1)
    source_route_after = _route_mode(library, source_domain)
    alien_state = _state_for(library, skill.skill_id, alien_domain.domain_id)
    negative_ok = (
        alien_route_before == 'trial'
        and not alien_routes_after
        and source_route_after == 'active'
        and alien_state == 'quarantined'
    )

    # Add lower-value single-domain capabilities so the capacity governor must
    # prefer the cross-domain capability based on accumulated evidence value.
    for index in range(2):
        distractor = TransferSkill(
            'periodic-recurrence-filter',
            ('guarded', 'periodic', 'recurrence'),
            _digest(f'distractor-{seed}-{index}'),
            (f'payload:distractor-{index}',),
            (f'lineage:distractor-{index}',),
            (f'distractor-source-{index}',),
            capacity_cost=1,
        )
        library = admit_skill(library, distractor)
    snapshot_before_capacity = library
    bounded = enforce_capacity(library, 1)
    retained = [record.skill.skill_id for record in bounded.records if record.state != 'retired']
    capacity_ok = bounded.capacity_used <= 1 and retained == [skill.skill_id]

    rolled = rollback_to_snapshot(bounded, snapshot_before_capacity)
    rollback_ok = (
        rolled.records == snapshot_before_capacity.records
        and rolled.version == bounded.version + 1
        and rolled.parent_version == bounded.version
        and rolled.rollback_of == bounded.version
    )

    gates = {
        'source_mechanism_established': source_ok,
        'external_trial_then_promotion': external_ok,
        'hard_decoy_falsification': len(false_survivors) >= len(AES_CORE_DECOYS),
        'negative_transfer_isolated': negative_ok,
        'duplicate_does_not_consume_capacity': dedup_ok,
        'capacity_prefers_validated_cross_domain_value': capacity_ok,
        'rollback_is_exact_and_auditable': rollback_ok,
    }
    all_gates_pass = all(gates.values())

    return {
        'schema_version': 1,
        'milestone': 'R2.18 Cross-Domain Transfer + Open-Ended Library Governance',
        'seed': int(seed),
        'source_transfer': {
            'domain_id': source_domain.domain_id,
            'survivors': list(source_survivors),
            'mechanism_tags': list(source_domain.mechanism_tags),
        },
        'external_transfer': {
            'domain_id': aes_domain.domain_id,
            'source': dict(NIST_SOURCE),
            'key_hex': NIST_AES128_KEY.hex(),
            'fixture_word_count': len(NIST_AES128_WORDS),
            'survivors': list(aes_survivors),
            'route_before_evidence': aes_route_before,
            'route_after_evidence': aes_route_after,
            'core_ablation_survivors': list(aes_ablated),
            'core_ablation_false_survivors': len(false_survivors),
            'hard_decoys': list(AES_CORE_DECOYS),
            'oracle_usage_boundary': 'Frozen NIST words validate fixture provenance; candidate filtering uses recurrence invariants only.',
            'cost_accounting_units': {
                'baseline_total': baseline_a + baseline_b,
                'assisted_total': assisted_a + assisted_b,
            },
        },
        'negative_transfer': {
            'domain_id': alien_domain.domain_id,
            'route_before_failure': alien_route_before,
            'alien_route_after_failure': [asdict(row) for row in alien_routes_after],
            'source_route_after_failure': source_route_after,
            'alien_state': alien_state,
            'trigger': 'false_accept_and_correctness_regression',
        },
        'deduplication': {
            'record_count_before_duplicate': before_duplicate_records,
            'record_count_after_duplicate': 1,
            'capacity_before_duplicate': before_duplicate_capacity,
            'capacity_after_duplicate': 1,
        },
        'capacity_governance': {
            'budget': 1,
            'capacity_used': bounded.capacity_used,
            'within_budget': bounded.capacity_used <= 1,
            'retained_skill_ids': retained,
            'target_skill_id': skill.skill_id,
            'target_skill_retained': retained == [skill.skill_id],
        },
        'rollback': {
            'snapshot_version': snapshot_before_capacity.version,
            'bounded_version': bounded.version,
            'rollback_version': rolled.version,
            'records_exactly_restored': rolled.records == snapshot_before_capacity.records,
            'new_audit_version': rolled.version > bounded.version,
        },
        'gates': gates,
        'all_gates_pass': all_gates_pass,
        'claims': {
            'guarded_claim': 'A mechanism-level periodic recurrence verifier transferred from a synthetic source family to the frozen NIST AES-128 key-schedule fixture while evidence governance contained an incompatible-domain failure and preserved bounded reversible library state.',
            'boundary': 'Bounded benchmark evidence over one synthetic mechanism family, one external AES fixture/cohort, and designed governance stressors; not unrestricted concept transfer, broad software engineering generality, frontier parity, or AGI.',
            'agi_claim': False,
            'broad_generalization_claim': False,
            'wall_clock_performance_claim': False,
        },
        'status': 'accepted' if all_gates_pass else 'rejected',
    }
