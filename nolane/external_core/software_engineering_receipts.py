from __future__ import annotations

from typing import Any

from nolane.external_core.software_engineering import (
    EngineeringEvidenceKind,
    EngineeringClosureReceipt,
    SoftwareEngineeringClosureEngine,
)


PARENT_PROTOCOL_ID = "external.software_engineering.closure"
PROTOCOL_ID = "external.software_engineering.canonical_receipt_boundary"
PROTOCOL_VERSION = "0.1.0"


def _canonical_roundtrip(receipt: Any, *, label: str) -> Any:
    to_state = getattr(receipt, "to_state", None)
    from_state = getattr(type(receipt), "from_state", None)
    if not callable(to_state) or not callable(from_state):
        raise ValueError(f"{label} integrity requires canonical state codec")
    try:
        restored = from_state(to_state())
    except Exception as exc:
        raise ValueError(f"{label} integrity validation failed") from exc
    if restored != receipt:
        raise ValueError(f"{label} integrity round-trip mismatch")
    return restored


def _validate_coding_semantics(receipt: Any) -> None:
    if not bool(getattr(receipt, "ready", False)):
        return
    if tuple(getattr(receipt, "reasons", ())):
        raise ValueError("coding readiness semantics are inconsistent with ready state")
    verification = getattr(receipt, "verification", None)
    if verification is None:
        raise ValueError("coding readiness semantics require verification")
    if not bool(getattr(verification, "passed", False)):
        raise ValueError("coding readiness semantics cannot be ready after failed verification")
    if int(getattr(verification, "false_accepts", 0)) != 0:
        raise ValueError("coding readiness semantics cannot accept false accepts")
    if int(getattr(verification, "regressions", 0)) != 0:
        raise ValueError("coding readiness semantics cannot accept regressions")


def _validate_ui_semantics(receipt: Any) -> None:
    if not bool(getattr(receipt, "ready", False)):
        return
    if tuple(getattr(receipt, "reasons", ())):
        raise ValueError("UI readiness semantics are inconsistent with ready state")
    if not tuple(getattr(receipt, "observation_ids", ())):
        raise ValueError("UI readiness semantics require observations")
    if not tuple(getattr(receipt, "quality_evidence_ids", ())):
        raise ValueError("UI readiness semantics require quality evidence")


class CanonicalReceiptClosureEngine(SoftwareEngineeringClosureEngine):
    """Closure boundary that distrusts even well-typed upstream receipt objects.

    Cross-surface receipts are round-tripped through their canonical codec before
    the base closure sees them. This proves content digest integrity and rejects
    direct dataclass construction with forged digest/state. Additional semantic
    consistency checks reject impossible positive Coding/UI states.
    """

    def assess(
        self,
        *,
        patch: Any,
        coding_readiness: Any,
        transaction_id: str,
        current_source_revision: str,
        required_attestation_kinds: tuple[EngineeringEvidenceKind, ...],
        attestation_ids: tuple[str, ...],
        require_debug: bool = False,
        debug_resolution: Any | None = None,
        require_ui: bool = False,
        ui_readiness: Any | None = None,
    ) -> EngineeringClosureReceipt:
        coding = _canonical_roundtrip(coding_readiness, label="coding readiness")
        _validate_coding_semantics(coding)

        debug = debug_resolution
        if require_debug and debug_resolution is not None:
            debug = _canonical_roundtrip(debug_resolution, label="debug resolution")

        ui = ui_readiness
        if require_ui and ui_readiness is not None:
            ui = _canonical_roundtrip(ui_readiness, label="UI readiness")
            _validate_ui_semantics(ui)

        return super().assess(
            patch=patch,
            coding_readiness=coding,
            transaction_id=transaction_id,
            current_source_revision=current_source_revision,
            required_attestation_kinds=required_attestation_kinds,
            attestation_ids=attestation_ids,
            require_debug=require_debug,
            debug_resolution=debug,
            require_ui=require_ui,
            ui_readiness=ui,
        )


__all__ = ("CanonicalReceiptClosureEngine",)
