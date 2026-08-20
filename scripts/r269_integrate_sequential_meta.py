from __future__ import annotations

from pathlib import Path


def patch_adapter() -> None:
    path = Path('cogcoder/r269_causal_basis_adapter.py')
    text = path.read_text(encoding='utf-8')
    marker = "_CLAIM_SCOPE = ('r268_verified_adaptive_basis', 'globally_minimal', 'proof_ledger_complete')\n"
    addition = marker + "_ALLOWED_ADAPTER_TYPES = frozenset(('causal_basis_v1', 'verified_meta_episode_v1'))\n"
    if '_ALLOWED_ADAPTER_TYPES' not in text:
        if text.count(marker) != 1:
            raise SystemExit('unexpected R2.69 adapter constant boundary')
        text = text.replace(marker, addition, 1)
    old = "        if self.adapter_type != 'causal_basis_v1':\n            raise ValueError('unsupported adapter_type')\n"
    new = "        if self.adapter_type not in _ALLOWED_ADAPTER_TYPES:\n            raise ValueError('unsupported adapter_type')\n"
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit('unexpected PortableExperience adapter boundary')
    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8')


def patch_matcher() -> None:
    path = Path('cogcoder/r269_meta_learning_kernel.py')
    text = path.read_text(encoding='utf-8')
    old = """        if portable.role_count != len(signature.role_names):
            out.append(MatchedPrior(portable, False, 0, 'role_cardinality_mismatch'))
            continue
        required = _binary_ops(portable.canonical_expression)
"""
    new = """        if portable.role_count != len(signature.role_names):
            out.append(MatchedPrior(portable, False, 0, 'role_cardinality_mismatch'))
            continue
        if portable.adapter_type == 'verified_meta_episode_v1':
            scope = frozenset(portable.claim_scope)
            domain_ok = f'numeric_domain={signature.numeric_domain}' in scope
            if signature.numeric_domain == 'finite_integer':
                exact_domain = 'finite_integer_values=' + ','.join(map(str, signature.finite_integer_values))
                domain_ok = domain_ok and exact_domain in scope
            if not domain_ok:
                out.append(MatchedPrior(portable, False, 0, 'verified_meta_domain_mismatch'))
                continue
        required = _binary_ops(portable.canonical_expression)
"""
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit('unexpected R2.69 matcher boundary')
    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8')


def patch_lazy_scratch_runtime() -> None:
    path = Path('cogcoder/r269_transfer_runtime.py')
    text = path.read_text(encoding='utf-8')
    if 'def _scratch_information_floor(' in text:
        compile(text, str(path), 'exec')
        return

    marker = """    return rows


def _predict(expr: Expr, context: Mapping[str, object]) -> tuple[bool, int | float | None]:
"""
    helper = """    return rows


def _scratch_information_floor(
    signature: PublicTaskSignature,
    config: MetaLearningConfig,
) -> list[_Hypothesis]:
    \"\"\"Bounded shallow scratch sentinel used only for transfer-query safety.

    It preserves generic scratch discrimination without materializing the full
    bounded search frontier.  It is never scratch selection authority.
    \"\"\"
    floor_config = MetaLearningConfig(
        max_diagnostic_queries=config.max_diagnostic_queries,
        transfer_candidate_cap=config.transfer_candidate_cap,
        scratch_candidate_cap=min(config.scratch_candidate_cap, 32),
        scratch_max_depth=min(config.scratch_max_depth, 1),
        min_scratch_partitions=config.min_scratch_partitions,
    )
    return _scratch_hypotheses(signature, floor_config)


def _predict(expr: Expr, context: Mapping[str, object]) -> tuple[bool, int | float | None]:
"""
    if marker not in text:
        raise SystemExit('scratch sentinel insertion boundary drifted')
    text = text.replace(marker, helper, 1)

    old_init = """    transfer = _transfer_hypotheses_many(compatible, signature, config.transfer_candidate_cap)
    scratch = _scratch_hypotheses(signature, config)
    transfer_initial = len(transfer)
    scratch_initial = len(scratch)
    ledger = SharedObservationLedger(signature)
"""
    new_init = """    transfer = _transfer_hypotheses_many(compatible, signature, config.transfer_candidate_cap)
    transfer_initial = len(transfer)
    scratch_materialized = not bool(transfer)
    scratch = (
        _scratch_hypotheses(signature, config)
        if scratch_materialized
        else _scratch_information_floor(signature, config)
    )
    scratch_initial = len(scratch)
    ledger = SharedObservationLedger(signature)
"""
    if old_init not in text:
        raise SystemExit('episode initialization boundary drifted')
    text = text.replace(old_init, new_init, 1)

    old_abandon = """            if not transfer and before_priors:
                contradictions += 1
                abandoned = True
                # All already purchased diagnostic observations are eligible for
                # scratch continuation. This is the concrete shared-evidence
                # credit, not an extra oracle call.
                reused_count = sum(observation.phase == 'diagnostic' for observation in ledger.observations)
        scratch = _filter(scratch, semantic, row.observed)
"""
    new_abandon = """            if not transfer and before_priors:
                contradictions += 1
                abandoned = True
                # All already purchased diagnostic observations are eligible for
                # scratch continuation. This is the concrete shared-evidence
                # credit, not an extra oracle call. Only now is full scratch
                # materialized and all purchased diagnostic evidence replayed.
                reused_count = sum(observation.phase == 'diagnostic' for observation in ledger.observations)
                full_scratch = _scratch_hypotheses(signature, config)
                scratch_initial = len(full_scratch)
                scratch = full_scratch
                scratch_materialized = True
                for observation in ledger.observations:
                    if (
                        observation.phase != 'diagnostic'
                        or observation.status != 'ok'
                        or observation.observed is None
                    ):
                        continue
                    observed_context = dict(
                        zip(signature.role_names, observation.context_values, strict=True)
                    )
                    scratch = _filter(scratch, observed_context, observation.observed)
                continue
        scratch = _filter(scratch, semantic, row.observed)
"""
    if old_abandon not in text:
        raise SystemExit('transfer abandonment boundary drifted')
    text = text.replace(old_abandon, new_abandon, 1)

    old_select = """    elif len(scratch) == 1 and ledger.physical_oracle_calls >= 1:
        selected = scratch[0]
        mode = 'scratch_after_transfer' if abandoned else 'scratch'
"""
    new_select = """    elif scratch_materialized and len(scratch) == 1 and ledger.physical_oracle_calls >= 1:
        selected = scratch[0]
        mode = 'scratch_after_transfer' if abandoned else 'scratch'
"""
    if old_select not in text:
        raise SystemExit('scratch selection boundary drifted')
    text = text.replace(old_select, new_select, 1)

    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    patch_adapter()
    patch_matcher()
    patch_lazy_scratch_runtime()
    print('R269_SEQUENTIAL_META_INTEGRATION_PATCHED')
