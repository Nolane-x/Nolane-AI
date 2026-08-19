from __future__ import annotations

from pathlib import Path

PATH = Path("cogcoder/r269_transfer_runtime.py")
text = PATH.read_text(encoding="utf-8")

replacements = []

replacements.append((
'''@dataclass(frozen=True, slots=True)
class _Hypothesis:
    expression: Expr
    hypothesis_id: str
    origin: str
    repair_distance: int = 0
''',
'''@dataclass(frozen=True, slots=True)
class _Hypothesis:
    expression: Expr
    hypothesis_id: str
    origin: str
    repair_distance: int = 0
    prior_digests: tuple[str, ...] = ()
'''))

replacements.append((
'''def _dedupe(rows: Sequence[_Hypothesis], cap: int, signature: PublicTaskSignature) -> list[_Hypothesis]:
    by_key: dict[str, _Hypothesis] = {}
    for row in rows:
        key = _structural_key(row.expression, signature)
        old = by_key.get(key)
        if old is None or (row.repair_distance, row.hypothesis_id) < (old.repair_distance, old.hypothesis_id):
            by_key[key] = row
    return sorted(by_key.values(), key=lambda row: (row.repair_distance, row.hypothesis_id))[:int(cap)]


def _transfer_hypotheses(portable: PortableExperience, signature: PublicTaskSignature, cap: int) -> list[_Hypothesis]:
    bases = [(portable.canonical_expression, 0)] + [
        (expr, 1) for expr in _mutations(portable.canonical_expression, signature.allowed_binary_ops)
    ]
    rows: list[_Hypothesis] = []
    for expr, distance in bases:
        for permutation in itertools.permutations(signature.role_names):
            rewritten = _rewrite(expr, dict(zip(portable.canonical_roles, permutation, strict=True)))
            rows.append(_Hypothesis(rewritten, 'transfer.' + expr_digest(rewritten), 'transfer', distance))
    return _dedupe(rows, int(cap), signature)
''',
'''def _dedupe(rows: Sequence[_Hypothesis], cap: int, signature: PublicTaskSignature) -> list[_Hypothesis]:
    by_key: dict[str, _Hypothesis] = {}
    contributors: dict[str, set[str]] = {}
    for row in rows:
        key = _structural_key(row.expression, signature)
        contributors.setdefault(key, set()).update(row.prior_digests)
        old = by_key.get(key)
        if old is None or (row.repair_distance, row.hypothesis_id) < (old.repair_distance, old.hypothesis_id):
            by_key[key] = row
    merged = [
        _Hypothesis(
            row.expression,
            row.hypothesis_id,
            row.origin,
            row.repair_distance,
            tuple(sorted(contributors[key])),
        )
        for key, row in by_key.items()
    ]
    return sorted(merged, key=lambda row: (row.repair_distance, row.hypothesis_id))[:int(cap)]


def _transfer_hypotheses(portable: PortableExperience, signature: PublicTaskSignature, cap: int) -> list[_Hypothesis]:
    bases = [(portable.canonical_expression, 0)] + [
        (expr, 1) for expr in _mutations(portable.canonical_expression, signature.allowed_binary_ops)
    ]
    rows: list[_Hypothesis] = []
    for expr, distance in bases:
        for permutation in itertools.permutations(signature.role_names):
            rewritten = _rewrite(expr, dict(zip(portable.canonical_roles, permutation, strict=True)))
            rows.append(
                _Hypothesis(
                    rewritten,
                    'transfer.' + expr_digest(rewritten),
                    'transfer',
                    distance,
                    (portable.portable_digest,),
                )
            )
    return _dedupe(rows, int(cap), signature)


def _transfer_hypotheses_many(
    portables: Sequence[PortableExperience],
    signature: PublicTaskSignature,
    cap: int,
) -> list[_Hypothesis]:
    if not portables:
        return []
    # Each compatible prior gets an equal opportunity to contribute at each
    # ranked position.  This keeps the total cap proof-distinct and prevents a
    # syntactically prolific prior from starving another before target evidence.
    per_prior = [
        _transfer_hypotheses(portable, signature, int(cap))
        for portable in sorted(portables, key=lambda row: row.portable_digest)
    ]
    interleaved: list[_Hypothesis] = []
    max_len = max(map(len, per_prior), default=0)
    for index in range(max_len):
        for rows in per_prior:
            if index < len(rows):
                interleaved.append(rows[index])
    return _dedupe(interleaved, int(cap), signature)


def _prior_digests(rows: Sequence[_Hypothesis]) -> frozenset[str]:
    return frozenset(digest for row in rows for digest in row.prior_digests)
'''))

replacements.append((
'''    compatible = [row.portable for row in matches if row.compatible]
    prior = compatible[0] if compatible else None
    transfer = _transfer_hypotheses(prior, signature, config.transfer_candidate_cap) if prior else []
    scratch = _scratch_hypotheses(signature, config)
''',
'''    compatible_matches = [row for row in matches if row.compatible]
    compatible = [row.portable for row in compatible_matches]
    single_prior_digest = compatible[0].portable_digest if len(compatible) == 1 else None
    match_score_by_digest = {
        row.portable.portable_digest: row.compatibility_score for row in compatible_matches
    }
    transfer = _transfer_hypotheses_many(compatible, signature, config.transfer_candidate_cap)
    scratch = _scratch_hypotheses(signature, config)
'''))

replacements.append((
'''        if row.status != 'ok' or row.observed is None:
            if prior:
                registry.quarantine(prior.portable_digest, reason=row.status, regret=1)
                quarantine = True
            return _receipt(
                False,
                'transfer' if prior else 'scratch',
                None,
                prior.portable_digest if prior else None,
                ledger,
                transfer_initial,
                scratch_initial,
                reused_count,
                contradictions,
                quarantine,
                row.status,
            )

        semantic = dict(zip(signature.role_names, row.context_values, strict=True))
        if transfer:
            transfer = _filter(transfer, semantic, row.observed)
            if not transfer and prior:
                contradictions += 1
                abandoned = True
                # All already purchased diagnostic observations are eligible for
                # scratch continuation. This is the concrete shared-evidence
                # credit, not an extra oracle call.
                reused_count = sum(observation.phase == 'diagnostic' for observation in ledger.observations)
                registry.quarantine(prior.portable_digest, reason='transfer_hypothesis_eliminated', regret=1)
                quarantine = True
        scratch = _filter(scratch, semantic, row.observed)
''',
'''        if row.status != 'ok' or row.observed is None:
            # Oracle/process failures are not evidence that any particular prior
            # is wrong.  Fail closed without poisoning reusable prior state.
            return _receipt(
                False,
                'transfer' if compatible else 'scratch',
                None,
                single_prior_digest,
                ledger,
                transfer_initial,
                scratch_initial,
                reused_count,
                contradictions,
                quarantine,
                row.status,
            )

        semantic = dict(zip(signature.role_names, row.context_values, strict=True))
        if transfer:
            before_priors = _prior_digests(transfer)
            transfer = _filter(transfer, semantic, row.observed)
            after_priors = _prior_digests(transfer)
            eliminated_priors = before_priors - after_priors
            for digest in sorted(eliminated_priors):
                registry.quarantine(digest, reason='transfer_hypothesis_eliminated', regret=0)
            if eliminated_priors:
                contradictions += len(eliminated_priors)
                quarantine = True
            if not transfer and before_priors:
                abandoned = True
                # All already purchased diagnostic observations are eligible for
                # scratch continuation. This is the concrete shared-evidence
                # credit, not an extra oracle call.
                reused_count = sum(observation.phase == 'diagnostic' for observation in ledger.observations)
        scratch = _filter(scratch, semantic, row.observed)
'''))

replacements.append((
'''    if selected is None:
        return _receipt(
            False,
            'scratch_after_transfer' if abandoned else ('transfer' if prior else 'scratch'),
            None,
            prior.portable_digest if prior else None,
            ledger,
            transfer_initial,
            scratch_initial,
            reused_count,
            contradictions,
            quarantine,
            'diagnostic_ambiguity',
        )

    passed, terminal_reason, terminal_calls = _terminal_verify(selected, terminal_contexts, oracle, ledger)
    if not passed:
        if mode == 'transfer' and prior:
            registry.quarantine(prior.portable_digest, reason=terminal_reason, regret=terminal_calls)
            quarantine = True
        return _receipt(
            False,
            mode,
            None,
            prior.portable_digest if prior else None,
            ledger,
            transfer_initial,
            scratch_initial,
            reused_count,
            contradictions,
            quarantine,
            terminal_reason,
            terminal_calls,
        )

    reason = (
        'accepted_transfer'
        if mode == 'transfer'
        else ('accepted_scratch_after_transfer' if mode == 'scratch_after_transfer' else 'accepted_scratch')
    )
    return _receipt(
        True,
        mode,
        selected.expression,
        prior.portable_digest if mode == 'transfer' and prior else None,
        ledger,
        transfer_initial,
        scratch_initial,
        reused_count,
        contradictions,
        quarantine,
        reason,
        terminal_calls,
    )
''',
'''    selected_prior_digest: str | None = None
    if selected is not None and mode == 'transfer' and selected.prior_digests:
        selected_prior_digest = sorted(
            selected.prior_digests,
            key=lambda digest: (-match_score_by_digest.get(digest, 0), digest),
        )[0]

    if selected is None:
        return _receipt(
            False,
            'scratch_after_transfer' if abandoned else ('transfer' if compatible else 'scratch'),
            None,
            single_prior_digest,
            ledger,
            transfer_initial,
            scratch_initial,
            reused_count,
            contradictions,
            quarantine,
            'diagnostic_ambiguity',
        )

    passed, terminal_reason, terminal_calls = _terminal_verify(selected, terminal_contexts, oracle, ledger)
    if not passed:
        if mode == 'transfer':
            for digest in selected.prior_digests:
                registry.quarantine(digest, reason=terminal_reason, regret=terminal_calls)
                quarantine = True
        return _receipt(
            False,
            mode,
            None,
            selected_prior_digest,
            ledger,
            transfer_initial,
            scratch_initial,
            reused_count,
            contradictions,
            quarantine,
            terminal_reason,
            terminal_calls,
        )

    reason = (
        'accepted_transfer'
        if mode == 'transfer'
        else ('accepted_scratch_after_transfer' if mode == 'scratch_after_transfer' else 'accepted_scratch')
    )
    return _receipt(
        True,
        mode,
        selected.expression,
        selected_prior_digest,
        ledger,
        transfer_initial,
        scratch_initial,
        reused_count,
        contradictions,
        quarantine,
        reason,
        terminal_calls,
    )
'''))

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one exact patch boundary, found {count}")
    text = text.replace(old, new)

compile(text, str(PATH), "exec")
PATH.write_text(text, encoding="utf-8")
