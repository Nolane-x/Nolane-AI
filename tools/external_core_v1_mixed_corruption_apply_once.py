from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "nolane/external_core/observation.py"


def replace_once(old: str, new: str) -> None:
    text = TARGET.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement target, found {count}: {old[:120]!r}")
    TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "from dataclasses import dataclass\n",
    "from dataclasses import dataclass, replace\n",
)

replace_once(
    '''def _surface_digest_map(envelope: CanonicalObservationEnvelope) -> dict[str, str]:
    return {
        "registry": envelope.registry_digest,
        "authority-graph": envelope.authority_graph_digest,
        "source-state": envelope.source_state_frontier_digest,
        "evidence": envelope.evidence_frontier_digest,
        "artifact": envelope.artifact_frontier_digest,
        "freshness": envelope.freshness_fence_frontier_digest,
        "handoff": envelope.handoff_frontier_digest,
        "work-trace": envelope.work_trace_frontier_digest,
    }


def validate_observation_completeness(
''',
    '''def _surface_digest_map(envelope: CanonicalObservationEnvelope) -> dict[str, str]:
    return {
        "registry": envelope.registry_digest,
        "authority-graph": envelope.authority_graph_digest,
        "source-state": envelope.source_state_frontier_digest,
        "evidence": envelope.evidence_frontier_digest,
        "artifact": envelope.artifact_frontier_digest,
        "freshness": envelope.freshness_fence_frontier_digest,
        "handoff": envelope.handoff_frontier_digest,
        "work-trace": envelope.work_trace_frontier_digest,
    }


def _surface_shape_anomaly_explains_integrity_failure(
    envelope: CanonicalObservationEnvelope,
) -> bool:
    """Return true only when removing duplicate/unknown receipts restores exact integrity."""

    rows: list[SurfaceObservationReceipt] = []
    seen: set[str] = set()
    for receipt in envelope.surface_receipts:
        if not isinstance(receipt, SurfaceObservationReceipt):
            return False
        if receipt.surface_kind not in REQUIRED_SURFACE_KINDS:
            continue
        if receipt.surface_kind in seen:
            continue
        seen.add(receipt.surface_kind)
        rows.append(receipt)

    repaired = replace(envelope, surface_receipts=tuple(rows))
    try:
        repaired.validate_integrity()
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    return True


def _forged_receipt_anomaly_explains_integrity_failure(
    envelope: CanonicalObservationEnvelope,
) -> bool:
    """Return true only when canonicalizing forged receipt bytes restores exact envelope integrity."""

    rows: list[SurfaceObservationReceipt] = []
    repaired_any = False
    for receipt in envelope.surface_receipts:
        if not isinstance(receipt, SurfaceObservationReceipt):
            return False
        try:
            receipt.validate_integrity()
        except (AttributeError, KeyError, TypeError, ValueError):
            try:
                repaired = SurfaceObservationReceipt.create(
                    surface_kind=receipt.surface_kind,
                    provider_id=receipt.provider_id,
                    provider_version=receipt.provider_version,
                    source_locator=receipt.source_locator,
                    scope_digest=receipt.scope_digest,
                    observed_state_digest=receipt.observed_state_digest,
                    enumeration_complete=receipt.enumeration_complete,
                    observed_epoch=receipt.observed_epoch,
                )
            except (AttributeError, KeyError, TypeError, ValueError):
                return False
            rows.append(repaired)
            repaired_any = True
        else:
            rows.append(receipt)

    if not repaired_any:
        return False
    repaired_envelope = replace(envelope, surface_receipts=tuple(rows))
    try:
        repaired_envelope.validate_integrity()
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    return True


def validate_observation_completeness(
''',
)

replace_once(
    '''    if envelope_integrity_error is not None and not any(
        row.code in malformed_surface_codes for row in findings
    ):
        raise envelope_integrity_error
''',
    '''    if envelope_integrity_error is not None:
        has_categorical_surface_shape = any(
            row.code in malformed_surface_codes for row in findings
        )
        if (
            not has_categorical_surface_shape
            or not _surface_shape_anomaly_explains_integrity_failure(envelope)
        ):
            raise envelope_integrity_error
''',
)

replace_once(
    '''    if envelope_integrity_error is not None and not any(
        row.code == "OBSERVATION_RECEIPT_FORGED" for row in findings
    ):
        raise envelope_integrity_error
''',
    '''    if envelope_integrity_error is not None:
        has_categorical_forgery = any(
            row.code == "OBSERVATION_RECEIPT_FORGED" for row in findings
        )
        if (
            not has_categorical_forgery
            or not _forged_receipt_anomaly_explains_integrity_failure(envelope)
        ):
            raise envelope_integrity_error
''',
)

print("External Core v1 mixed-corruption hardening patch applied with exact guards")
