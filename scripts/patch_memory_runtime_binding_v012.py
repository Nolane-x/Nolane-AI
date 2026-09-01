from pathlib import Path

path = Path("nolane/memory/runtime_binding.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one runtime-binding anchor, got {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    '''    validated = LearningSubstrate.from_state(\n        registry=registry,\n        events=events,\n        state=full_state,\n    )\n''',
    '''    validated = LearningSubstrate.from_state(\n        registry=registry,\n        events=events,\n        state=full_state,\n        learning_authority=authority,\n    )\n''',
)
replace_once(
    '''        skills=skills,\n        experiences=experiences,\n    )\n    _copy_validated_overlay(target, validated)\n    target.learning_authority = authority\n''',
    '''        skills=skills,\n        experiences=experiences,\n        learning_authority=authority,\n    )\n    _copy_validated_overlay(target, validated)\n''',
)

path.write_text(text, encoding="utf-8")
print("patched", path)
