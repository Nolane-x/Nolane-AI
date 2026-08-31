from __future__ import annotations

import runpy
from pathlib import Path


try:
    runpy.run_path(".github/e_acting_effect_authority_patch.py", run_name="__main__")
except SystemExit as exc:
    message = str(exc)
    expected = "expected patch anchor missing in CURRENT/E_ACTING.md"
    if expected not in message:
        raise


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    if old not in source:
        raise SystemExit(f"v2 patch anchor missing in {path}: {old[:120]!r}")
    if source.count(old) != 1:
        raise SystemExit(f"v2 patch anchor is not unique in {path}: {old[:120]!r}")
    file_path.write_text(source.replace(old, new, 1), encoding="utf-8")


# Preserve the existing session accounting definition in this wave. Physical
# effect authority is hardened independently; widening the meaning of
# max_external_core_calls belongs to a separately proven budget wave.
replace_once(
    "nolane/external_core/execution.py",
    "if is_external_effect and session.counters.external_core_calls >= session.budget.max_external_core_calls:",
    "if is_external and session.counters.external_core_calls >= session.budget.max_external_core_calls:",
)
replace_once(
    "nolane/external_core/execution.py",
    "return self._budget_terminal(session, 'external-effect budget exhausted')",
    "return self._budget_terminal(session, 'external-core budget exhausted')",
)
replace_once(
    "nolane/external_core/execution.py",
    "external_core_calls=session.counters.external_core_calls + (1 if is_external_effect else 0),",
    "external_core_calls=session.counters.external_core_calls + (1 if is_external else 0),",
)

# The receipt-provenance wave already owns invariant 21; restart reconciliation
# is 22 on the actual branch. Append authority invariants without renumbering
# accepted history.
replace_once(
    "CURRENT/E_ACTING.md",
    "22. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.\n",
    "22. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.\n23. Risk authority is monotone with effect authority: READ requires at least R1, local mutation R2, external mutation R3, and irreversible effect R4. An execution contract cannot encode a weaker risk class than its effect class.\n24. Physical effect classification is enforced again at the transactional runtime before any ledger or core mutation. Only bounded built-in reads are admitted as READ; filesystem writes are local mutations; process, external, custom, and unknown handlers are external-like by default. Caller-supplied effect/risk labels cannot downgrade this floor.\n",
)
