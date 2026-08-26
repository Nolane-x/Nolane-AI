from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from nolane.core.canonical_digest import canonical_digest


@dataclass(frozen=True, slots=True)
class FacadeBinding:
    component_id: str
    canonical_module: str
    legacy_module: str
    public_symbols: tuple[str, ...]
    component_version: str = "0.0.0"

    def __post_init__(self) -> None:
        if not self.component_id or not self.canonical_module or not self.legacy_module or not self.public_symbols:
            raise ValueError("facade binding requires component/module/symbol identity")
        if self.component_version != "0.0.0":
            raise ValueError("Epoch-0 facades must bootstrap at component version 0.0.0")

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "canonical_module": self.canonical_module,
            "legacy_module": self.legacy_module,
            "public_symbols": list(self.public_symbols),
            "component_version": self.component_version,
        }


@dataclass(frozen=True, slots=True)
class FacadeParityReport:
    binding_count: int
    import_failures: tuple[str, ...]
    symbol_failures: tuple[str, ...]
    identity_mismatches: tuple[str, ...]
    digest: str

    @property
    def clean(self) -> bool:
        return not self.import_failures and not self.symbol_failures and not self.identity_mismatches

    def payload(self) -> dict[str, Any]:
        return {
            "binding_count": self.binding_count,
            "import_failures": list(self.import_failures),
            "symbol_failures": list(self.symbol_failures),
            "identity_mismatches": list(self.identity_mismatches),
        }

    def __post_init__(self) -> None:
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("facade parity report digest mismatch")


def build_active_facade_bindings() -> tuple[FacadeBinding, ...]:
    return (
        FacadeBinding("external.individual_evolution", "nolane.external_core.individual_evolution", "cogcoder.organization.individual_evolution", ("IndividualEvolutionControlPlane",)),
        FacadeBinding("external.coding.control", "nolane.external_core.coding", "cogcoder.organization.coding", ("CodingControlPlane",)),
        FacadeBinding("external.debugging", "nolane.external_core.debugging", "cogcoder.organization.debugging", ("DebugControlPlane",)),
        FacadeBinding("external.ui_ux", "nolane.external_core.ui_ux", "cogcoder.organization.ui", ("UIControlPlane",)),
        FacadeBinding("external.assurance", "nolane.external_core.assurance", "cogcoder.organization.assurance", ("AssuranceControlPlane",)),
        FacadeBinding("external.operations", "nolane.external_core.operations", "cogcoder.organization.operations", ("OperationsControlPlane",)),
        FacadeBinding("external.research", "nolane.external_core.research", "cogcoder.organization.research", ("ResearchControlPlane",)),
        FacadeBinding("evaluation.scaling", "nolane.evaluation.scaling", "cogcoder.organization.evaluation", ("EvaluationScalingControlPlane",)),
        FacadeBinding("evaluation.regimes", "nolane.evaluation.regimes", "cogcoder.organization.evaluation_regimes", ("BenchmarkRegimeRegistry",)),
        FacadeBinding("evaluation.evidence", "nolane.evaluation.evidence", "cogcoder.organization.evaluation_evidence", ("EvaluationEvidenceLedger",)),
        FacadeBinding("evaluation.stress", "nolane.evaluation.stress", "cogcoder.organization.evaluation_stress", ("LongHorizonStressLedger",)),
        FacadeBinding("evaluation.parameters", "nolane.evaluation.parameters", "cogcoder.organization.evaluation_parameters", ("ParameterScalingAuthority",)),
        FacadeBinding("evaluation.release", "nolane.evaluation.release", "cogcoder.organization.evaluation_release", ("EvaluationReleaseLedger",)),
        FacadeBinding("evaluation.claims", "nolane.evaluation.claims", "cogcoder.organization.evaluation_claims", ("ClaimBoundaryEngine",)),
        FacadeBinding("evaluation.campaign", "nolane.evaluation.campaign", "cogcoder.organization.campaign", ("EvaluationCampaignControlPlane",)),
    )


def validate_active_facades() -> FacadeParityReport:
    import_failures: list[str] = []
    symbol_failures: list[str] = []
    mismatches: list[str] = []
    bindings = build_active_facade_bindings()
    for row in bindings:
        try:
            canonical = importlib.import_module(row.canonical_module)
            legacy = importlib.import_module(row.legacy_module)
        except Exception as exc:
            import_failures.append(f"{row.component_id}:{type(exc).__name__}:{exc}")
            continue
        if getattr(canonical, "COMPONENT_VERSION", None) != row.component_version:
            symbol_failures.append(f"{row.component_id}:COMPONENT_VERSION")
        if getattr(canonical, "MIGRATED_FROM", None) != row.legacy_module:
            symbol_failures.append(f"{row.component_id}:MIGRATED_FROM")
        for symbol in row.public_symbols:
            if not hasattr(canonical, symbol) or not hasattr(legacy, symbol):
                symbol_failures.append(f"{row.component_id}:{symbol}")
                continue
            if getattr(canonical, symbol) is not getattr(legacy, symbol):
                mismatches.append(f"{row.component_id}:{symbol}")
    payload = {
        "binding_count": len(bindings),
        "import_failures": import_failures,
        "symbol_failures": symbol_failures,
        "identity_mismatches": mismatches,
    }
    return FacadeParityReport(
        binding_count=len(bindings),
        import_failures=tuple(import_failures),
        symbol_failures=tuple(symbol_failures),
        identity_mismatches=tuple(mismatches),
        digest=canonical_digest(payload),
    )
