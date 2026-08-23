from __future__ import annotations

import pytest

from cogcoder.refoundation.census import CensusKind, RepositoryCensus, SourceCensusRecord
from cogcoder.refoundation.compatibility import build_bootstrap_parity_report
from cogcoder.refoundation.migration import LegacyDisposition, ReviewDepth


def test_bootstrap_parity_report_has_zero_identity_contract_drift() -> None:
    report = build_bootstrap_parity_report()
    assert report.source_identity_count == 67
    assert report.manifest_identity_count == 67
    assert report.missing_agent_ids == ()
    assert report.extra_agent_ids == ()
    assert report.field_mismatches == ()
    assert report.clean
    assert len(report.digest) == 64


def test_repository_census_rejects_duplicate_paths() -> None:
    row = SourceCensusRecord(
        path="cogcoder/organization/runtime.py",
        kind=CensusKind.SOURCE,
        disposition=LegacyDisposition.COMPATIBILITY,
        review_depth=ReviewDepth.LINE_REVIEWED,
    )
    with pytest.raises(ValueError):
        RepositoryCensus((row, row))


def test_repository_census_reports_exact_coverage_without_guessing_missing_paths() -> None:
    census = RepositoryCensus(
        (
            SourceCensusRecord(path="a.py", kind=CensusKind.SOURCE),
            SourceCensusRecord(path="b.json", kind=CensusKind.RESULT),
        )
    )
    report = census.coverage(("a.py", "b.json", "c.md"))
    assert report.tracked_count == 3
    assert report.censused_count == 2
    assert report.missing_paths == ("c.md",)
    assert report.coverage_ratio == pytest.approx(2 / 3)
    assert not report.complete


def test_destructive_phase_is_blocked_until_every_tracked_path_is_censused() -> None:
    census = RepositoryCensus((SourceCensusRecord(path="a.py", kind=CensusKind.SOURCE),))
    with pytest.raises(PermissionError):
        census.require_complete(("a.py", "missing.py"))


def test_complete_census_does_not_make_keep_paths_deletable() -> None:
    row = SourceCensusRecord(
        path="cogcoder/r269_meta_learning_kernel.py",
        kind=CensusKind.HISTORICAL_SOURCE,
        disposition=LegacyDisposition.KEEP,
        review_depth=ReviewDepth.LINE_REVIEWED,
        blob_sha="0123456789abcdef0123456789abcdef01234567",
    )
    census = RepositoryCensus((row,))
    assert census.coverage((row.path,)).complete
    assert not row.as_legacy_path_record().destructive_action_allowed


def test_census_digest_is_stable_across_input_order() -> None:
    a = SourceCensusRecord(path="a.py", kind=CensusKind.SOURCE)
    b = SourceCensusRecord(path="b.py", kind=CensusKind.TEST)
    assert RepositoryCensus((a, b)).digest == RepositoryCensus((b, a)).digest
