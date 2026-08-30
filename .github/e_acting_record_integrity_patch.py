from __future__ import annotations

from pathlib import Path


def replace_exact(path_s: str, old: str, new: str, *, count: int = 1) -> None:
    path = Path(path_s)
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(
            f"{path_s}: expected {count} occurrences, found {actual}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new, count), encoding="utf-8")


protocol = "nolane/external_core/acting_protocol.py"
replace_exact(protocol, 'COMPONENT_VERSION = "0.1.0"', 'COMPONENT_VERSION = "0.1.1"')

old_record_state = '''    def to_state(self) -> dict[str, Any]:
        return {
            "contract": self.contract.to_state(),
            "phase": self.phase.value,
            "lease": None if self.lease is None else self.lease.to_state(),
            "authorization_ref": self.authorization_ref,
            "precondition_evidence_refs": list(self.precondition_evidence_refs),
            "outcome_ref": self.outcome_ref,
            "outcome_success": self.outcome_success,
            "postcondition_evidence_refs": list(self.postcondition_evidence_refs),
            "verifier_level": int(self.verifier_level),
            "attempts": self.attempts,
            "local_mutations": self.local_mutations,
            "external_effects": self.external_effects,
            "commit_ref": self.commit_ref,
            "rollback_ref": self.rollback_ref,
            "failure_reason": self.failure_reason,
            "event_receipt_ids": list(self.event_receipt_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ActionRecord":
        lease = state.get("lease")
        return cls(
            contract=ExecutionContract.from_state(state["contract"]),
            phase=ActionPhase(str(state.get("phase", ActionPhase.PROPOSED.value))),
            lease=None if lease is None else ExecutionLease.from_state(lease),
            authorization_ref=str(state.get("authorization_ref", "")),
            precondition_evidence_refs=tuple(str(x) for x in state.get("precondition_evidence_refs", ())),
            outcome_ref=str(state.get("outcome_ref", "")),
            outcome_success=state.get("outcome_success"),
            postcondition_evidence_refs=tuple(str(x) for x in state.get("postcondition_evidence_refs", ())),
            verifier_level=VerifierLevel(int(state.get("verifier_level", 0))),
            attempts=int(state.get("attempts", 0)),
            local_mutations=int(state.get("local_mutations", 0)),
            external_effects=int(state.get("external_effects", 0)),
            commit_ref=str(state.get("commit_ref", "")),
            rollback_ref=str(state.get("rollback_ref", "")),
            failure_reason=str(state.get("failure_reason", "")),
            event_receipt_ids=tuple(str(x) for x in state.get("event_receipt_ids", ())),
        )
'''
new_record_state = '''    def _state_payload(self) -> dict[str, Any]:
        return {
            "contract": self.contract.to_state(),
            "phase": self.phase.value,
            "lease": None if self.lease is None else self.lease.to_state(),
            "authorization_ref": self.authorization_ref,
            "precondition_evidence_refs": list(self.precondition_evidence_refs),
            "outcome_ref": self.outcome_ref,
            "outcome_success": self.outcome_success,
            "postcondition_evidence_refs": list(self.postcondition_evidence_refs),
            "verifier_level": int(self.verifier_level),
            "attempts": self.attempts,
            "local_mutations": self.local_mutations,
            "external_effects": self.external_effects,
            "commit_ref": self.commit_ref,
            "rollback_ref": self.rollback_ref,
            "failure_reason": self.failure_reason,
            "event_receipt_ids": list(self.event_receipt_ids),
        }

    @property
    def digest(self) -> str:
        return canonical_digest(self._state_payload())

    def to_state(self) -> dict[str, Any]:
        return {**self._state_payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ActionRecord":
        lease = state.get("lease")
        row = cls(
            contract=ExecutionContract.from_state(state["contract"]),
            phase=ActionPhase(str(state.get("phase", ActionPhase.PROPOSED.value))),
            lease=None if lease is None else ExecutionLease.from_state(lease),
            authorization_ref=str(state.get("authorization_ref", "")),
            precondition_evidence_refs=tuple(str(x) for x in state.get("precondition_evidence_refs", ())),
            outcome_ref=str(state.get("outcome_ref", "")),
            outcome_success=state.get("outcome_success"),
            postcondition_evidence_refs=tuple(str(x) for x in state.get("postcondition_evidence_refs", ())),
            verifier_level=VerifierLevel(int(state.get("verifier_level", 0))),
            attempts=int(state.get("attempts", 0)),
            local_mutations=int(state.get("local_mutations", 0)),
            external_effects=int(state.get("external_effects", 0)),
            commit_ref=str(state.get("commit_ref", "")),
            rollback_ref=str(state.get("rollback_ref", "")),
            failure_reason=str(state.get("failure_reason", "")),
            event_receipt_ids=tuple(str(x) for x in state.get("event_receipt_ids", ())),
        )
        supplied_digest = str(state.get("digest", ""))
        if supplied_digest != row.digest:
            raise ValueError("action record digest mismatch")
        return row
'''
replace_exact(protocol, old_record_state, new_record_state)

old_validate = '''    def _validate_state(self) -> None:
        referenced: set[str] = set()
        for row in self.records():
            if row.lease is not None and row.lease.action_id != row.action_id:
                raise ValueError("action contains lease for a different action")
            self.validate_chain(row.action_id)
            referenced.update(row.event_receipt_ids)
        if referenced != set(self._events):
            raise ValueError("protocol state contains orphan execution events")
'''
new_validate = '''    @staticmethod
    def _single_event(history: tuple[ExecutionEvent, ...], event_type: str) -> ExecutionEvent | None:
        matches = tuple(event for event in history if event.event_type == event_type)
        if len(matches) > 1:
            raise ValueError(f"action lifecycle contains duplicate {event_type} events")
        return matches[0] if matches else None

    def _validate_record_projection(self, row: ActionRecord) -> None:
        history = self.events(row.action_id)
        if not history or history[0].event_type != "proposed" or history[0].phase is not ActionPhase.PROPOSED:
            raise ValueError("action record has no canonical proposed event")

        proposed_payload_digest = canonical_digest(
            {
                "contract_digest": canonical_digest(row.contract.to_state()),
                "semantic_digest": row.contract.semantic_digest,
            }
        )
        if history[0].payload_digest != proposed_payload_digest:
            raise ValueError("action record contract disagrees with proposed event")

        lease_acquired = self._single_event(history, "lease_acquired")
        if lease_acquired is None:
            if row.authorization_ref or row.lease is not None:
                raise ValueError("action record lease/authorization disagrees with lifecycle events")
        else:
            if lease_acquired.evidence_refs != (row.authorization_ref,):
                raise ValueError("action record authorization disagrees with lease event")
            if row.lease is None:
                raise ValueError("action record lease missing despite lease event")

        preconditions = self._single_event(history, "preconditions_verified")
        expected_precondition_refs = () if preconditions is None else preconditions.evidence_refs
        if row.precondition_evidence_refs != expected_precondition_refs:
            raise ValueError("action record precondition evidence disagrees with lifecycle event")
        if preconditions is not None:
            expected_payload = canonical_digest(
                {"declared_preconditions": list(row.contract.preconditions)}
            )
            if preconditions.payload_digest != expected_payload:
                raise ValueError("action record preconditions disagree with lifecycle event")

        execution = self._single_event(history, "execution_started")
        if execution is None:
            if row.attempts or row.local_mutations or row.external_effects:
                raise ValueError("action record execution counters disagree with lifecycle events")
        else:
            expected_payload = canonical_digest(
                {
                    "attempt": row.attempts,
                    "local_mutations": row.local_mutations,
                    "external_effects": row.external_effects,
                    "effect_class": row.contract.effect_class.value,
                }
            )
            if execution.payload_digest != expected_payload:
                raise ValueError("action record execution counters disagree with lifecycle event")

        outcome = self._single_event(history, "outcome_observed")
        if outcome is None:
            if row.outcome_ref or row.outcome_success is not None:
                raise ValueError("action record outcome disagrees with lifecycle events")
        else:
            if row.outcome_success is None or outcome.evidence_refs != (row.outcome_ref,):
                raise ValueError("action record outcome disagrees with lifecycle event")
            expected_payload = canonical_digest({"success": bool(row.outcome_success)})
            if outcome.payload_digest != expected_payload:
                raise ValueError("action record outcome result disagrees with lifecycle event")

        postconditions = self._single_event(history, "postconditions_verified")
        if postconditions is None:
            if row.postcondition_evidence_refs or row.verifier_level is not VerifierLevel.V0:
                raise ValueError("action record postcondition state disagrees with lifecycle events")
        else:
            if postconditions.evidence_refs != row.postcondition_evidence_refs:
                raise ValueError("action record postcondition evidence disagrees with lifecycle event")
            expected_payload = canonical_digest(
                {
                    "verifier_level": int(row.verifier_level),
                    "declared_postconditions": list(row.contract.postconditions),
                }
            )
            if postconditions.payload_digest != expected_payload:
                raise ValueError("action record verifier state disagrees with lifecycle event")

        committed = self._single_event(history, "committed")
        if committed is None:
            if row.commit_ref:
                raise ValueError("action record commit disagrees with lifecycle events")
        else:
            if committed.evidence_refs != (row.commit_ref,):
                raise ValueError("action record commit reference disagrees with lifecycle event")
            if committed.payload_digest != canonical_digest({"outcome_ref": row.outcome_ref}):
                raise ValueError("action record commit outcome disagrees with lifecycle event")

        rolled_back = self._single_event(history, "rolled_back")
        degraded = self._single_event(history, "degraded")
        cancelled = self._single_event(history, "cancelled")
        terminal_events = tuple(x for x in (committed, rolled_back, degraded, cancelled) if x is not None)
        if len(terminal_events) > 1:
            raise ValueError("action record contains multiple terminal lifecycle events")
        if rolled_back is not None:
            if rolled_back.evidence_refs != (row.rollback_ref,):
                raise ValueError("action record rollback reference disagrees with lifecycle event")
            if rolled_back.payload_digest != canonical_digest({"failure_reason": row.failure_reason}):
                raise ValueError("action record rollback reason disagrees with lifecycle event")
        elif degraded is not None:
            if degraded.evidence_refs != (row.rollback_ref,):
                raise ValueError("action record recovery reference disagrees with lifecycle event")
            expected_payload = canonical_digest(
                {"failure_reason": row.failure_reason, "recovery_plan": row.contract.recovery_plan}
            )
            if degraded.payload_digest != expected_payload:
                raise ValueError("action record degraded recovery disagrees with lifecycle event")
        elif cancelled is not None:
            if cancelled.payload_digest != canonical_digest({"reason": row.failure_reason}):
                raise ValueError("action record cancellation reason disagrees with lifecycle event")
        elif row.rollback_ref or row.failure_reason:
            raise ValueError("action record terminal failure state has no lifecycle event")

    def _validate_state(self) -> None:
        referenced: set[str] = set()
        for row in self.records():
            if row.lease is not None and row.lease.action_id != row.action_id:
                raise ValueError("action contains lease for a different action")
            self.validate_chain(row.action_id)
            self._validate_record_projection(row)
            referenced.update(row.event_receipt_ids)
        if referenced != set(self._events):
            raise ValueError("protocol state contains orphan execution events")
'''
replace_exact(protocol, old_validate, new_validate)

workflow = ".github/workflows/refoundation-e-acting.yml"
replace_exact(
    workflow,
    '''            tests/test_refoundation_acting_protocol.py \\
            tests/test_refoundation_acting_workspace.py \\
''',
    '''            tests/test_refoundation_acting_protocol.py \\
            tests/test_refoundation_acting_record_integrity.py \\
            tests/test_refoundation_acting_workspace.py \\
''',
)

current = "CURRENT/E_ACTING.md"
replace_exact(
    current,
    '| Transaction Protocol | `nolane/external_core/acting_protocol.py` | `0.1.0` |',
    '| Transaction Protocol | `nolane/external_core/acting_protocol.py` | `0.1.1` |',
)
replace_exact(
    current,
    "9. Lifecycle receipts are append-only and hash-chained.\n",
    "9. Lifecycle receipts are append-only and hash-chained; persisted `ActionRecord` state is content-addressed and must project exactly from those lifecycle events.\n",
)

spec = "docs/superpowers/specs/2026-08-30-refoundation-e-acting-transactional-runtime-design.md"
replace_exact(
    spec,
    "For each action, receipts form a hash chain. `from_state()` validates event digests, ids, sequence, previous-digest linkage, ownership, phase/head agreement, and rejects orphan events.\n\nThis is tamper-evident rather than cryptographically signed.",
    "For each action, receipts form a hash chain. `from_state()` validates event digests, ids, sequence, previous-digest linkage, ownership, phase/head agreement, and rejects orphan events. Persisted `ActionRecord` snapshots are independently content-addressed and then cross-checked against the immutable lifecycle events: the proposed contract, authorization, pre/postcondition evidence, execution counters, outcome, verifier state, and terminal references cannot be rebound by recomputing only the local record digest.\n\nThis is tamper-evident rather than cryptographically signed.",
)
