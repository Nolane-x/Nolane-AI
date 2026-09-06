from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "nolane" / "external_core" / "observation.py"
text = TARGET.read_text(encoding="utf-8")

replacements = (
    (
        '''def validate_observation_completeness(\n    envelope: CanonicalObservationEnvelope,\n    *,\n    expected_component_ids: Sequence[str],\n    observed_surface_digests: Mapping[str, str],\n    expected_scope_digests: Mapping[str, str] | None = None,\n) -> tuple[ObservationFinding, ...]:\n    envelope.validate_integrity()\n    expected_components = _validated_component_ids(expected_component_ids)\n''',
        '''def validate_observation_completeness(\n    envelope: CanonicalObservationEnvelope,\n    *,\n    expected_component_ids: Sequence[str],\n    observed_surface_digests: Mapping[str, str],\n    expected_scope_digests: Mapping[str, str] | None = None,\n) -> tuple[ObservationFinding, ...]:\n    envelope_integrity_error: Exception | None = None\n    try:\n        envelope.validate_integrity()\n    except (AttributeError, KeyError, TypeError, ValueError) as exc:\n        envelope_integrity_error = exc\n\n    expected_components = _validated_component_ids(expected_component_ids)\n''',
    ),
    (
        '''        if expected_scope_digests is not None:\n            expected_scope = expected_scope_digests.get(kind)\n            if expected_scope is None or receipt.scope_digest != expected_scope:\n                findings.append(\n                    ObservationFinding(\n                        code="OBSERVATION_SURFACE_SCOPE_MISMATCH",\n                        detail="surface receipt scope does not match the canonical declared scope",\n                        subject_id=kind,\n                    )\n                )\n\n    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))\n\n\ndef validate_observation_provenance(\n''',
        '''        if expected_scope_digests is not None:\n            expected_scope = expected_scope_digests.get(kind)\n            if expected_scope is None or receipt.scope_digest != expected_scope:\n                findings.append(\n                    ObservationFinding(\n                        code="OBSERVATION_SURFACE_SCOPE_MISMATCH",\n                        detail="surface receipt scope does not match the canonical declared scope",\n                        subject_id=kind,\n                    )\n                )\n\n    malformed_surface_codes = {\n        "OBSERVATION_SURFACE_DUPLICATE",\n        "OBSERVATION_SURFACE_UNEXPECTED",\n    }\n    if envelope_integrity_error is not None and not any(\n        row.code in malformed_surface_codes for row in findings\n    ):\n        raise envelope_integrity_error\n\n    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))\n\n\ndef validate_observation_provenance(\n''',
    ),
)

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one completeness hardening target, found {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")
print("A8 completeness diagnostic reachability hardening applied")
