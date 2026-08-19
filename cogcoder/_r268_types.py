from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from .r256_operator_dsl import Expr
from .r258_intervention_discovery import InterventionSpec

@dataclass(frozen=True, slots=True)
class NecessityCertificate:
    basis_semantic_profile_ids: tuple[str, ...]
    subset_semantic_profile_ids: tuple[str, ...]
    subset_cardinality: int
    exposed_fields: tuple[str, ...]
    evidence_digest: str
    proof_kind: str
    witness_digest: str
    witness_rows: tuple[int, int]

@dataclass(frozen=True, slots=True)
class BasisCollisionCertificate:
    semantic_profile_ids: tuple[str, ...]
    basis_cardinality: int
    exposed_fields: tuple[str, ...]
    evidence_digest: str
    proof_kind: str
    witness_digest: str
    witness_rows: tuple[int, int]

@dataclass(frozen=True, slots=True)
class InterventionProfile:
    intervention: InterventionSpec
    discovery_outputs: tuple[object, ...]
    validation_outputs: tuple[object, ...]
    semantic_profile_id: str

    def __post_init__(self) -> None:
        base=str(self.semantic_profile_id).strip()
        if not base:
            raise ValueError('semantic_profile_id must be non-empty')
        payload={
            'observed_semantic_id':base,
            'intervention_id':self.intervention.intervention_id,
        }
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'))
        object.__setattr__(self,'semantic_profile_id',f'profile.{hashlib.sha256(raw.encode()).hexdigest()}')

@dataclass(frozen=True, slots=True)
class AdaptiveCausalBasisCandidate:
    interventions: tuple[InterventionSpec, ...]
    profiles: tuple[InterventionProfile, ...]
    semantic_profile_ids: tuple[str, ...]
    basis_size: int
    shared_positions: tuple[int, ...]
    expression: Expr
    expression_digest: str
    used_fields: tuple[str, ...]
    selection_cases: int
    selection_exact: int
    validation_cases: int
    validation_exact: int
    composition_candidates_considered: int

@dataclass(frozen=True, slots=True)
class AdaptiveCausalBasisStructureReceipt:
    passed: bool
    selected: AdaptiveCausalBasisCandidate | None
    selected_basis_size: int
    globally_minimal: bool
    necessity_certificates: tuple[NecessityCertificate, ...]
    unresolved_lower_order: tuple[str, ...]
    legal_interventions: int
    semantic_profiles: int
    intervention_candidates_considered: int
    bases_considered: int
    composition_candidates_considered: int
    oracle_calls: int
    false_accepts: int
    reason: str
    learning_query_keys: frozenset[str] = frozenset()
    validation_targets: tuple[object, ...] = ()
    lower_basis_count: int = 0
    lower_basis_certified: int = 0
    lower_basis_inconclusive: int = 0
    lower_basis_universe_digest: str = ''
    proof_ledger_complete: bool = False
    lower_basis_certificates: tuple[BasisCollisionCertificate, ...] = ()
    trainable_parameter_count: int = 0

@dataclass(frozen=True, slots=True)
class AdaptiveCausalBasisReceipt:
    passed: bool
    structure: AdaptiveCausalBasisStructureReceipt
    expression: Expr | None
    probe_expressions: tuple[Expr, ...]
    probe_candidates_considered: tuple[int, ...]
    probe_validation_cases: int
    probe_validation_exact: int
    final_validation_cases: int
    final_validation_exact: int
    reason: str
    selected_basis_size: int
    globally_minimal: bool
    false_accepts: int = 0
    trainable_parameter_count: int = 0
    oracle_calls_total: int = 0
    terminal_probe_validation_cases: int = 0
    terminal_probe_validation_exact: int = 0
