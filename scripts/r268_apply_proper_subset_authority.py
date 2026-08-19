from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/_r268_runtime.py')
text = path.read_text()

old = "from ._r268_proof import build_public_target_collision_certificate"
new = "from ._r268_proof import build_public_target_collision_certificate,has_public_target_collision"
if text.count(old) != 1:
    raise SystemExit('R2.68 proof import surface changed concurrently')
text = text.replace(old, new, 1)

old = "cert=build_public_target_collision_certificate(basis_semantic_profile_ids=ids,subset_semantic_profile_ids=ids,exposed_fields=fields,examples=examples)"
new = "collision=has_public_target_collision(examples,fields)"
if text.count(old) != 1:
    raise SystemExit('R2.68 global lower-basis collision surface changed concurrently')
text = text.replace(old, new, 1)

old = "if cert is not None:\n                certs.append(cert);lower_ledger.append((k,ledger_identity,'collision_certified'));continue"
new = "if collision:\n                lower_ledger.append((k,ledger_identity,'collision_certified'));continue"
if text.count(old) != 1:
    raise SystemExit('R2.68 global lower-basis certificate surface changed concurrently')
text = text.replace(old, new, 1)

needle = "candidate=AdaptiveCausalBasisCandidate(tuple(p.intervention for p in basis),tuple(basis),ids,k,shared,search.expression,expr_digest(search.expression),used,len(d_targets),exact,len(v_targets),validation_exact,search.candidates_considered)\n            lower_rows="
if text.count(needle) != 1:
    raise SystemExit('R2.68 selected candidate surface changed concurrently')
insert = """candidate=AdaptiveCausalBasisCandidate(tuple(p.intervention for p in basis),tuple(basis),ids,k,shared,search.expression,expr_digest(search.expression),used,len(d_targets),exact,len(v_targets),validation_exact,search.candidates_considered)
            selected_certs=[];local_certificate_missing=False
            for subset_size in range(1,k):
                for subset_indexes in itertools.combinations(range(k),subset_size):
                    subset_profiles=tuple(basis[index] for index in subset_indexes)
                    subset_ids=tuple(profile.semantic_profile_id for profile in subset_profiles)
                    subset_shared=basis_shared_positions(schema,subset_profiles)
                    subset_fields=tuple(f'__p{i}' for i in range(subset_size))+tuple(schema.canonical_fields[index] for index in subset_shared)
                    subset_examples=composition_examples(schema,discovery,tuple(d_targets),subset_profiles,subset_shared,phase='discovery')
                    subset_cert=build_public_target_collision_certificate(
                        basis_semantic_profile_ids=ids,
                        subset_semantic_profile_ids=subset_ids,
                        exposed_fields=subset_fields,
                        examples=subset_examples,
                    )
                    if subset_cert is None:
                        local_certificate_missing=True
                        break
                    selected_certs.append(subset_cert)
                if local_certificate_missing:break
            lower_rows="""
text = text.replace(needle, insert, 1)

old = "proof_complete=k>1 and lower_count>0 and lower_certified==lower_count and lower_inconclusive==0\n            minimal=proof_complete;reason='adaptive_basis_discovered' if minimal else 'sufficient_but_minimality_inconclusive'"
new = "proof_complete=k>1 and lower_count>0 and lower_certified==lower_count and lower_inconclusive==0\n            expected_local_certificates=(1<<k)-2 if k>1 else 0\n            local_proof_complete=k>1 and not local_certificate_missing and len(selected_certs)==expected_local_certificates\n            minimal=proof_complete and local_proof_complete;reason='adaptive_basis_discovered' if minimal else 'sufficient_but_minimality_inconclusive'"
if text.count(old) != 1:
    raise SystemExit('R2.68 minimality authority surface changed concurrently')
text = text.replace(old, new, 1)

old = "passed=True,selected=candidate,selected_basis_size=k,globally_minimal=minimal,necessity_certificates=tuple(certs),"
new = "passed=True,selected=candidate,selected_basis_size=k,globally_minimal=minimal,necessity_certificates=tuple(selected_certs),"
if text.count(old) != 1:
    raise SystemExit('R2.68 selected certificate receipt surface changed concurrently')
text = text.replace(old, new, 1)

path.write_text(text)
print('R268_PROPER_SUBSET_AUTHORITY_PATCH_APPLIED')
