from __future__ import annotations

from cogcoder.refoundation.facades import build_active_facade_bindings, validate_active_facades


def test_active_facade_bindings_are_unique_and_explicit() -> None:
    bindings = build_active_facade_bindings()
    assert bindings
    assert len({row.component_id for row in bindings}) == len(bindings)
    assert len({row.canonical_module for row in bindings}) == len(bindings)
    assert all(row.canonical_module.startswith("nolane.") for row in bindings)
    assert all(row.legacy_module.startswith("cogcoder.organization.") for row in bindings)
    assert all(row.public_symbols for row in bindings)


def test_every_declared_active_facade_preserves_public_symbol_identity() -> None:
    bindings = build_active_facade_bindings()
    report = validate_active_facades()
    assert report.binding_count == len(bindings)
    assert report.import_failures == ()
    assert report.symbol_failures == ()
    assert report.identity_mismatches == ()
    assert report.clean
    assert len(report.digest) == 64
