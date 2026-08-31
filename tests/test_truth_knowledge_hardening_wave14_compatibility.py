from __future__ import annotations

from nolane.external_core.epistemic_defeasible_truth import (
    DEFEASIBLE_BINDING_MODE,
    DefeasibleTruthScope,
)
from nolane.external_core.epistemic_dependence_truth import DEPENDENCE_BINDING_MODE
from nolane.external_core.verification_defeasible_truth import (
    DefeasibleTruthVerificationLedger,
    DefeasibleTruthVerificationReceipt,
)
from nolane.external_core.verification_dependence_truth import DependenceTruthVerificationLedger


def test_a14_does_not_rewrite_a13_binding_mode_or_scope_type():
    assert DEFEASIBLE_BINDING_MODE == "defeasible-justification-provenance-lineage-temporal-v7"
    assert DEPENDENCE_BINDING_MODE != DEFEASIBLE_BINDING_MODE
    assert DefeasibleTruthScope.__module__ == "nolane.external_core.epistemic_defeasible_truth"


def test_a14_keeps_v7_verification_ledger_as_distinct_historical_type():
    assert DefeasibleTruthVerificationLedger is not DependenceTruthVerificationLedger
    assert DefeasibleTruthVerificationReceipt.__module__ == (
        "nolane.external_core.verification_defeasible_truth"
    )
