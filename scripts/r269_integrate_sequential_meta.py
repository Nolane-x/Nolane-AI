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

    old_signature = "def _scratch_hypotheses(signature: PublicTaskSignature, config: MetaLearningConfig) -> list[_Hypothesis]:\n    rows: list[_Hypothesis] = []\n    seen: set[str] = set()\n"
    new_signature = "def _scratch_hypotheses(\n    signature: PublicTaskSignature,\n    config: MetaLearningConfig,\n    *,\n    candidate_cap: int | None = None,\n) -> list[_Hypothesis]:\n    rows: list[_Hypothesis] = []\n    seen: set[str] = set()\n    cap = config.scratch_candidate_cap if candidate_cap is None else min(\n        config.scratch_candidate_cap, max(1, int(candidate_cap))\n    )\n"
    if old_signature in text:
        text = text.replace(old_signature, new_signature, 1)
    elif new_signature not in text:
        raise SystemExit('unexpected scratch generator signature boundary')

    old_cap = "        return len(rows) < config.scratch_candidate_cap\n"
    new_cap = "        return len(rows) < cap\n"
    if old_cap in text:
        text = text.replace(old_cap, new_cap, 1)
    elif new_cap not in text:
        raise SystemExit('unexpected scratch generator cap boundary')

    old_init = """    transfer = _transfer_hypotheses_many(compatible, signature, config.transfer_candidate_cap)
    scratch = _scratch_hypotheses(signature, config)
    transfer_initial = len(transfer)
    scratch_initial = len(scratch)
    ledger = SharedObservationLedger(signature)
    used: set[str] = set()
    abandoned = False
    contradictions = 0
    quarantine = False
    reused_count = 0
"""
    new_init = """    transfer = _transfer_hypotheses_many(compatible, signature, config.transfer_candidate_cap)
    transfer_initial = len(transfer)
    scratch_full_materialized = not bool(transfer)
    scratch_witness_cap = min(
        config.scratch_candidate_cap,
        max(8, 2 * config.min_scratch_partitions, 2 * len(signature.role_names)),
    )
    scratch = _scratch_hypotheses(
        signature,
        config,
        candidate_cap=None if scratch_full_materialized else scratch_witness_cap,
    )
    scratch_initial = len(scratch)
    ledger = SharedObservationLedger(signature)
    used: set[str] = set()
    abandoned = False
    contradictions = 0
    quarantine = False
    reused_count = 0

    def materialize_full_scratch() -> None:
        nonlocal scratch, scratch_initial, scratch_full_materialized
        if scratch_full_materialized:
            return
        full = _scratch_hypotheses(signature, config)
        # The witness pool is a deterministic prefix of the same generator.
        # Count unique scratch hypotheses considered, not duplicate regeneration.
        scratch_initial = max(scratch_initial, len(full))
        for observation in ledger.observations:
            if observation.phase != 'diagnostic' or observation.status != 'ok' or observation.observed is None:
                continue
            semantic = dict(zip(signature.role_names, observation.context_values, strict=True))
            full = _filter(full, semantic, observation.observed)
        scratch = full
        scratch_full_materialized = True
"""
    if old_init in text:
        text = text.replace(old_init, new_init, 1)
    elif new_init not in text:
        raise SystemExit('unexpected transfer/scratch initialization boundary')

    old_abandon = """            if not transfer and before_priors:
                contradictions += 1
                abandoned = True
                # All already purchased diagnostic observations are eligible for
                # scratch continuation. This is the concrete shared-evidence
                # credit, not an extra oracle call.
                reused_count = sum(observation.phase == 'diagnostic' for observation in ledger.observations)
        scratch = _filter(scratch, semantic, row.observed)

    selected: _Hypothesis | None = None
"""
    new_abandon = """            if not transfer and before_priors:
                contradictions += 1
                abandoned = True
                # All already purchased diagnostic observations are eligible for
                # scratch continuation. This is the concrete shared-evidence
                # credit, not an extra oracle call.
                reused_count = sum(observation.phase == 'diagnostic' for observation in ledger.observations)
                materialize_full_scratch()
        scratch = _filter(scratch, semantic, row.observed)

    if not (len(transfer) == 1 and ledger.physical_oracle_calls >= 1):
        # A scratch answer is authoritative only against the complete bounded
        # scratch pool. Successful transfer never pays this cost; fallback does.
        materialize_full_scratch()

    selected: _Hypothesis | None = None
"""
    if old_abandon in text:
        text = text.replace(old_abandon, new_abandon, 1)
    elif new_abandon not in text:
        raise SystemExit('unexpected negative-transfer fallback boundary')

    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    patch_adapter()
    patch_matcher()
    patch_lazy_scratch_runtime()
    print('R269_SEQUENTIAL_META_INTEGRATION_PATCHED')
