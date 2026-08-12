from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_eval_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "eval_r1_6_slice.py"
    spec = spec_from_file_location("eval_r1_6_slice", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_select_tasks_respects_split_namespace():
    mod = _load_eval_module()
    dev = mod.select_tasks("dev", 0, 2)
    fresh = mod.select_tasks("fresh", 0, 2)
    assert len(dev) == len(fresh) == 6
    assert {t.split for t in dev} == {"dev"}
    assert {t.split for t in fresh} == {"fresh"}
    assert {t.task_id for t in dev}.isdisjoint({t.task_id for t in fresh})
    assert {t.seed for t in dev}.isdisjoint({t.seed for t in fresh})


def test_evaluator_parser_accepts_fresh_split():
    mod = _load_eval_module()
    parser = mod.build_arg_parser()
    args = parser.parse_args([
        "--checkpoint", "x.pt",
        "--split", "fresh",
        "--start", "0",
        "--output", "out.json",
    ])
    assert args.split == "fresh"
