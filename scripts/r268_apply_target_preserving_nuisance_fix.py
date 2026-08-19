from __future__ import annotations

from pathlib import Path


runtime_path = Path('cogcoder/_r268_runtime.py')
runtime = runtime_path.read_text()
old_runtime = """        discovery_outputs=tuple(dv)
        if len({semantic_key((v,)) for v in discovery_outputs})<2:continue
        sid=hashlib.sha256(semantic_key(discovery_outputs).encode()).hexdigest();profiles.append(InterventionProfile(spec,tuple(dv),tuple(vv),sid))
"""
new_runtime = """        discovery_outputs=tuple(dv);validation_outputs=tuple(vv)
        if len({semantic_key((v,)) for v in discovery_outputs})<2:continue
        if all(
            equivalent(actual,expected)
            for actual,expected in zip(
                (*discovery_outputs,*validation_outputs),
                (*d_targets,*v_targets),
                strict=True,
            )
        ):continue
        sid=hashlib.sha256(semantic_key(discovery_outputs).encode()).hexdigest();profiles.append(InterventionProfile(spec,discovery_outputs,validation_outputs,sid))
"""
if runtime.count(old_runtime) != 1:
    raise SystemExit('R2.68 intervention-profile surface changed concurrently')
runtime_path.write_text(runtime.replace(old_runtime, new_runtime, 1))

benchmark_path = Path('benchmarks/kfigg/r268_adaptive_causal_basis.py')
benchmark = benchmark_path.read_text()
replacements = (
    ("('one-probe-sufficient',f1,o1,((1,2,3),(2,3,4),(-2,5,7),(4,-3,9),(5,2,11),(-3,-2,13)),((6,7,15),(-5,4,17),(8,-2,19)),((101,103,107),(-109,113,127),(131,-137,139)),1),",
     "('one-probe-nuisance-negative',f1,o1,((1,2,3),(2,3,4),(-2,5,7),(4,-3,9),(5,2,11),(-3,-2,13)),((6,7,15),(-5,4,17),(8,-2,19)),((101,103,107),(-109,113,127),(131,-137,139)),0),"),
    ("        all(row['passed'] for row in results),", "        results[0]['passed'] is False and all(row['passed'] for row in results[1:]),"),
    ("        selected==[1,2,3,4],", "        selected==[0,2,3,4],"),
    ("'mixed_cardinality_exact':selected==[1,2,3,4]", "'mixed_cardinality_exact':selected==[0,2,3,4]"),
)
for old, new in replacements:
    if benchmark.count(old) != 1:
        raise SystemExit(f'R2.68 benchmark surface changed concurrently: {old!r}')
    benchmark = benchmark.replace(old, new, 1)
benchmark_path.write_text(benchmark)
print('R268_TARGET_PRESERVING_NUISANCE_FIX_APPLIED')
