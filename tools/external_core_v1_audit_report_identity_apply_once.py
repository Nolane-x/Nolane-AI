from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected exactly one replacement target, found {count}: {old[:140]!r}"
        )
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


TARGET = "nolane/external_core/integration_admission_bundle.py"

replace_once(
    TARGET,
    '''@dataclass(frozen=True, slots=True)
class CanonicalAdmissionAuditReport:
''',
    '''def _exact_canonical_observation_digest(value: object) -> str:
    if type(value) is not str:
        raise ValueError("current observation audit observation digest must be an exact string")
    prefix = "canonical-observation-v1-"
    if not value.startswith(prefix):
        raise ValueError("current observation audit observation digest protocol identity mismatch")
    suffix = value[len(prefix) :]
    if len(suffix) != 64 or any(ch not in "0123456789abcdef" for ch in suffix):
        raise ValueError(
            "current observation audit observation digest must carry exactly 64 lowercase hexadecimal characters"
        )
    return value


@dataclass(frozen=True, slots=True)
class CanonicalAdmissionAuditReport:
''',
)

replace_once(
    TARGET,
    '''        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        if current_observation:
            if observation_digest is not None and (
                type(observation_digest) is not str or not observation_digest.strip()
            ):
                raise ValueError("current observation audit observation digest must be an exact non-empty string")
            if not rows and observation_digest is None:
                raise ValueError("clean current observation audit requires an exact observation digest")
        protocol = ADMISSION_AUDIT_PROTOCOL if current_observation else HISTORICAL_ADMISSION_AUDIT_PROTOCOL
''',
    '''        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        if type(current_observation) is not bool:
            raise ValueError("current_observation must be an exact boolean")
        if current_observation:
            if observation_digest is not None:
                observation_digest = _exact_canonical_observation_digest(observation_digest)
            if not rows and observation_digest is None:
                raise ValueError("clean current observation audit requires an exact observation digest")
        elif observation_digest is not None:
            raise ValueError("historical audit-v3 must not receive an observation digest witness")
        protocol = ADMISSION_AUDIT_PROTOCOL if current_observation else HISTORICAL_ADMISSION_AUDIT_PROTOCOL
''',
)

replace_once(
    TARGET,
    '''    def make_report(rows: Sequence[AdmissionAuditFinding]) -> CanonicalAdmissionAuditReport:
        return CanonicalAdmissionAuditReport.create(
            rows,
            current_observation=current_observation_mode,
            observation_digest=(
                None
                if current_observation_for_report is None
                else current_observation_for_report.digest
            ),
        )
''',
    '''    def make_report(rows: Sequence[AdmissionAuditFinding]) -> CanonicalAdmissionAuditReport:
        observation_digest: str | None = None
        if current_observation_for_report is not None:
            try:
                current_observation_for_report.validate_integrity()
                observation_digest = _exact_canonical_observation_digest(
                    current_observation_for_report.digest
                )
            except (AttributeError, KeyError, TypeError, ValueError):
                # A malformed or integrity-invalid current witness is failure evidence,
                # never a witness that may be rebound into the audit report.
                observation_digest = None
        return CanonicalAdmissionAuditReport.create(
            rows,
            current_observation=current_observation_mode,
            observation_digest=observation_digest,
        )
''',
)

TEST = "tests/test_external_core_a10_v1_crosslayer_audit.py"
replace_once(
    TEST,
    '''def test_v4_audit_digest_binds_exact_observation_digest() -> None:
    left = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=True,
        observation_digest="canonical-observation-v1-left",
    )
    right = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=True,
        observation_digest="canonical-observation-v1-right",
    )
''',
    '''def test_v4_audit_digest_binds_exact_observation_digest() -> None:
    left = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=True,
        observation_digest="canonical-observation-v1-" + ("1" * 64),
    )
    right = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=True,
        observation_digest="canonical-observation-v1-" + ("2" * 64),
    )
''',
)
replace_once(
    TEST,
    '''def test_historical_v3_audit_does_not_relabel_or_bind_observation_digest() -> None:
    left = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=False,
        observation_digest="ignored-left",
    )
    right = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=False,
        observation_digest="ignored-right",
    )
    assert left.protocol == right.protocol == "external-integration-admission-audit-v3"
    assert left.observation_digest is right.observation_digest is None
    assert left.digest == right.digest
    assert "observation_digest" not in left.to_state()
''',
    '''def test_historical_v3_audit_rejects_observation_digest_smuggling() -> None:
    with pytest.raises(ValueError, match="historical audit-v3"):
        admission_bundle.CanonicalAdmissionAuditReport.create(
            (),
            current_observation=False,
            observation_digest="canonical-observation-v1-" + ("3" * 64),
        )
''',
)
replace_once(
    TEST,
    '''    assert "CURRENT_OBSERVATION_WITNESS_INVALID" in {
        row.code for row in report.findings
    }
''',
    '''    assert "CURRENT_OBSERVATION_WITNESS_INVALID" in {
        row.code for row in report.findings
    }
    assert report.observation_digest is None
''',
)
replace_once(
    TEST,
    '''        observation_digest="canonical-observation-v1-fixed",
    )
    reverse = admission_bundle.CanonicalAdmissionAuditReport.create(
        tuple(reversed(rows)),
        current_observation=True,
        observation_digest="canonical-observation-v1-fixed",
''',
    '''        observation_digest="canonical-observation-v1-" + ("a" * 64),
    )
    reverse = admission_bundle.CanonicalAdmissionAuditReport.create(
        tuple(reversed(rows)),
        current_observation=True,
        observation_digest="canonical-observation-v1-" + ("a" * 64),
''',
)

DOC = "CURRENT/EXTERNAL_CORE.md"
replace_once(
    DOC,
    '''The current admission audit is `external-integration-admission-audit-v4`. A current v4 report binds the exact `external-canonical-observation-v1` envelope digest and revalidates observation integrity, A8 completeness, A9 provenance, A10 predecessor continuity and supplied sibling-fork evidence together with the existing A5/A6/A7 admission checks. Historical call shapes remain historical v3 evidence and are not auto-migrated or relabeled as v4. The frozen `external-integration-admission-v2` issuer remains component version `0.0.4`, and `external-integration-admission-bundle-v2` remains unchanged.''',
    '''The current admission audit is `external-integration-admission-audit-v4`. A current v4 report binds an observation digest only when the supplied or constructed `external-canonical-observation-v1` envelope passes canonical integrity; an integrity-invalid witness is recorded as failure evidence and its digest is not rebound into the report. A clean v4 report therefore always carries an exact canonical-observation-v1 digest and revalidates A8 completeness, A9 provenance, A10 predecessor continuity and supplied sibling-fork evidence together with the existing A5/A6/A7 admission checks. Historical call shapes remain historical v3 evidence and are not auto-migrated or relabeled as v4. The frozen `external-integration-admission-v2` issuer remains component version `0.0.4`, and `external-integration-admission-bundle-v2` remains unchanged.''',
)

DOC_TEST = "tests/test_external_core_a10_v1_document_contract.py"
replace_once(
    DOC_TEST,
    '''        "The current admission audit is `external-integration-admission-audit-v4`",
        "Historical call shapes remain historical v3 evidence",
''',
    '''        "The current admission audit is `external-integration-admission-audit-v4`",
        "A current v4 report binds an observation digest only when the supplied or constructed `external-canonical-observation-v1` envelope passes canonical integrity",
        "an integrity-invalid witness is recorded as failure evidence and its digest is not rebound into the report",
        "Historical call shapes remain historical v3 evidence",
''',
)

print("External Core v1 audit-report identity hardening applied with exact guards")
