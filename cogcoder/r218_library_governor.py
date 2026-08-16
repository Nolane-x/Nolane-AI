from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .r218_transfer_types import (
    DomainDescriptor,
    DomainEvidence,
    GovernedSkillRecord,
    OpenEndedLibraryVersion,
    RouteDecision,
    TransferObservation,
    TransferSkill,
)


def _next_version(library: OpenEndedLibraryVersion, records: tuple[GovernedSkillRecord, ...], reason: str) -> OpenEndedLibraryVersion:
    return OpenEndedLibraryVersion(
        library.version + 1,
        records,
        parent_version=library.version,
        reason=reason,
    )


def _source_evidence(skill: TransferSkill) -> tuple[DomainEvidence, ...]:
    return tuple(
        DomainEvidence(domain, 'active', reason='source_validated')
        for domain in skill.source_domains
    )


def admit_skill(library: OpenEndedLibraryVersion, skill: TransferSkill) -> OpenEndedLibraryVersion:
    records = list(library.records)
    for index, record in enumerate(records):
        if record.skill.skill_id != skill.skill_id:
            continue
        if record.skill.capacity_cost != skill.capacity_cost:
            raise ValueError('duplicate skill identity cannot change capacity_cost')
        merged = TransferSkill(
            record.skill.kind,
            record.skill.mechanism_tags,
            record.skill.behavior_digest,
            tuple(set(record.skill.payload_refs) | set(skill.payload_refs)),
            tuple(set(record.skill.provenance_lineages) | set(skill.provenance_lineages)),
            tuple(set(record.skill.source_domains) | set(skill.source_domains)),
            record.skill.capacity_cost,
        )
        by_domain = {row.domain_id: row for row in record.domain_evidence}
        for row in _source_evidence(merged):
            by_domain.setdefault(row.domain_id, row)
        records[index] = GovernedSkillRecord(
            merged,
            record.state,
            tuple(by_domain.values()),
            record.reason,
        )
        return _next_version(library, tuple(records), 'merge_duplicate_skill')
    records.append(GovernedSkillRecord(skill, 'active', _source_evidence(skill), 'admitted'))
    return _next_version(library, tuple(records), 'admit_skill')


def _overlap(skill: TransferSkill, domain: DomainDescriptor) -> float:
    left = set(skill.mechanism_tags)
    right = set(domain.mechanism_tags)
    if not left:
        return 0.0
    return len(left & right) / len(left)


def route_skills(
    library: OpenEndedLibraryVersion,
    domain: DomainDescriptor,
    *,
    max_capacity: int,
    min_overlap: float = 0.5,
    max_trials: int = 1,
) -> tuple[RouteDecision, ...]:
    if int(max_capacity) < 0 or int(max_trials) < 0:
        raise ValueError('route budgets must be non-negative')
    active: list[tuple[float, GovernedSkillRecord]] = []
    trials: list[tuple[float, GovernedSkillRecord]] = []
    for record in library.records:
        if record.state == 'retired':
            continue
        evidence = record.evidence_for(domain.domain_id)
        overlap = _overlap(record.skill, domain)
        if evidence is not None and evidence.state == 'quarantined':
            continue
        if evidence is not None and evidence.state == 'active':
            active.append((overlap, record))
        elif evidence is None and overlap + 1e-12 >= float(min_overlap):
            trials.append((overlap, record))

    active.sort(key=lambda item: (-item[0], item[1].skill.capacity_cost, item[1].skill.skill_id))
    trials.sort(key=lambda item: (-item[0], item[1].skill.capacity_cost, item[1].skill.skill_id))
    out: list[RouteDecision] = []
    used = 0
    for overlap, record in active:
        cost = record.skill.capacity_cost
        if used + cost > max_capacity:
            continue
        out.append(RouteDecision(record.skill.skill_id, 'active', overlap, 'validated_domain', cost))
        used += cost
    trial_count = 0
    for overlap, record in trials:
        if trial_count >= max_trials:
            break
        cost = record.skill.capacity_cost
        if used + cost > max_capacity:
            continue
        out.append(RouteDecision(record.skill.skill_id, 'trial', overlap, 'unseen_domain_mechanism_match', cost))
        used += cost
        trial_count += 1
    return tuple(out)


def _merge_domain_observations(
    existing: DomainEvidence | None,
    rows: tuple[TransferObservation, ...],
    *,
    min_window: int,
    min_cost_reduction: float,
    max_cost_regression: float,
) -> DomainEvidence:
    domain_id = rows[0].domain_id
    if existing is not None and existing.state == 'quarantined':
        return existing
    task_ids = set(() if existing is None else existing.task_ids)
    successes = 0 if existing is None else existing.successes
    failures = 0 if existing is None else existing.failures
    false_accepts = 0 if existing is None else existing.false_accepts
    baseline_total = 0 if existing is None else existing.baseline_cost_total
    assisted_total = 0 if existing is None else existing.assisted_cost_total

    immediate_reason = ''
    for row in rows:
        task_ids.add(row.task_id)
        success = bool(row.assisted_correct and not row.false_accept)
        successes += int(success)
        failures += int(not success)
        false_accepts += int(row.false_accept)
        baseline_total += row.baseline_cost
        assisted_total += row.assisted_cost
        if row.false_accept:
            immediate_reason = 'transfer_false_accept'
        elif row.baseline_correct and not row.assisted_correct:
            immediate_reason = 'transfer_accuracy_regression'
        elif row.baseline_correct and row.budget_exhausted:
            immediate_reason = 'transfer_budget_exhaustion'

    if immediate_reason:
        state = 'quarantined'
        reason = immediate_reason
    else:
        n = len(task_ids)
        reduction = 0.0 if baseline_total <= 0 else 1.0 - assisted_total / baseline_total
        if n >= min_window and baseline_total > 0 and assisted_total / baseline_total - 1.0 > max_cost_regression + 1e-12:
            state = 'quarantined'
            reason = 'transfer_cost_regression'
        elif n >= min_window and failures == 0 and false_accepts == 0 and reduction + 1e-12 >= min_cost_reduction:
            state = 'active'
            reason = 'validated_cross_domain_transfer'
        else:
            state = 'candidate'
            reason = 'evidence_window_open'
    return DomainEvidence(
        domain_id,
        state,
        tuple(task_ids),
        successes,
        failures,
        false_accepts,
        baseline_total,
        assisted_total,
        reason,
    )


def apply_transfer_observations(
    library: OpenEndedLibraryVersion,
    observations: Iterable[TransferObservation],
    *,
    min_window: int = 2,
    min_cost_reduction: float = 0.05,
    max_cost_regression: float = 0.10,
) -> OpenEndedLibraryVersion:
    if min_window < 1:
        raise ValueError('min_window must be positive')
    if min_cost_reduction < 0 or max_cost_regression < 0:
        raise ValueError('transfer thresholds must be non-negative')
    unique: dict[tuple[str, str, str], TransferObservation] = {}
    for row in tuple(observations):
        key = (row.task_id, row.domain_id, row.skill_id)
        previous = unique.get(key)
        if previous is not None and previous != row:
            raise ValueError('conflicting duplicate transfer observation')
        unique[key] = row
    if not unique:
        return library

    by_skill: dict[str, list[TransferObservation]] = {}
    known = {record.skill.skill_id for record in library.records}
    for row in unique.values():
        if row.skill_id not in known:
            raise ValueError(f'unknown skill_id: {row.skill_id}')
        by_skill.setdefault(row.skill_id, []).append(row)

    records: list[GovernedSkillRecord] = []
    for record in library.records:
        skill_rows = by_skill.get(record.skill.skill_id)
        if not skill_rows:
            records.append(record)
            continue
        evidence = {row.domain_id: row for row in record.domain_evidence}
        grouped: dict[str, list[TransferObservation]] = {}
        for row in skill_rows:
            grouped.setdefault(row.domain_id, []).append(row)
        for domain_id, rows in grouped.items():
            ordered = tuple(sorted(rows, key=lambda row: row.task_id))
            evidence[domain_id] = _merge_domain_observations(
                evidence.get(domain_id),
                ordered,
                min_window=min_window,
                min_cost_reduction=min_cost_reduction,
                max_cost_regression=max_cost_regression,
            )
        records.append(GovernedSkillRecord(record.skill, record.state, tuple(evidence.values()), record.reason))
    return _next_version(library, tuple(records), 'apply_transfer_observations')


def _record_value_density(record: GovernedSkillRecord) -> float:
    active = [row for row in record.domain_evidence if row.state == 'active']
    clean_uses = sum(row.successes for row in active)
    savings = sum(max(0, row.baseline_cost_total - row.assisted_cost_total) for row in active)
    validated_domains = len(active)
    quarantines = sum(row.state == 'quarantined' for row in record.domain_evidence)
    value = 10.0 * validated_domains + clean_uses + savings / 100.0 - 5.0 * quarantines
    return value / record.skill.capacity_cost


def enforce_capacity(library: OpenEndedLibraryVersion, capacity: int) -> OpenEndedLibraryVersion:
    if int(capacity) < 0:
        raise ValueError('capacity must be non-negative')
    ranked = sorted(
        (record for record in library.records if record.state != 'retired'),
        key=lambda record: (-_record_value_density(record), record.skill.capacity_cost, record.skill.skill_id),
    )
    keep: set[str] = set()
    used = 0
    for record in ranked:
        cost = record.skill.capacity_cost
        if used + cost <= capacity:
            keep.add(record.skill.skill_id)
            used += cost
    records = tuple(
        record if record.skill.skill_id in keep else replace(record, state='retired', reason='capacity_eviction')
        for record in library.records
    )
    if records == library.records:
        return library
    return _next_version(library, records, 'enforce_capacity')


def rollback_to_snapshot(
    current: OpenEndedLibraryVersion, snapshot: OpenEndedLibraryVersion
) -> OpenEndedLibraryVersion:
    return OpenEndedLibraryVersion(
        current.version + 1,
        snapshot.records,
        parent_version=current.version,
        rollback_of=current.version,
        reason=f'rollback_to_version_{snapshot.version}',
    )
