from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one anchor in {path}, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


substrate = Path("nolane/memory/learning_substrate.py")
replace_once(
    substrate,
    '''        if actor.region != self.lifecycle.REGION:\n            raise PermissionError("verified memory admission requires a Memory/Context actor")\n        if evidence is None:\n''',
    '''        if actor.region != self.lifecycle.REGION:\n            raise PermissionError("verified memory admission requires a Memory/Context actor")\n        if actor.agent_id != "memory.chief":\n            raise PermissionError("reactivating governed memory requires Memory Chief authority")\n        if evidence is None:\n''',
)

workflow = Path(".github/workflows/memory-learning-substrate.yml")
replace_once(
    workflow,
    '''            tests/test_memory_learning_verified_admission_forgetting_v012.py\n            tests/test_refoundation_component_versions.py\n''',
    '''            tests/test_memory_learning_verified_admission_forgetting_v012.py\n            tests/test_memory_learning_lease_transactionality_v012.py\n            tests/test_refoundation_component_versions.py\n''',
)

print("patched v0.0.12 transactionality and gate")
