from pathlib import Path

from research.r256_external_operator_transfer import run_transfer


def test_external_oracle_transfer_synthesizes_from_io_without_parsing_source(tmp_path: Path):
    source = tmp_path / 'mathutils.py'
    source.write_text(
        "def clamp(x, lower=float('-inf'), upper=float('inf')):\n"
        "    if upper < lower:\n"
        "        raise ValueError('bad bounds')\n"
        "    if x < lower:\n"
        "        return lower\n"
        "    if x > upper:\n"
        "        return upper\n"
        "    return x\n",
        encoding='utf-8',
    )
    result = run_transfer(
        source,
        repository='example/external-oracle',
        commit='deadbeef',
        function_name='clamp',
    )
    assert result['passed'] is True
    assert result['function_name'] == 'clamp'
    assert result['training_cases'] >= 6
    assert result['heldout_cases'] >= 20
    assert result['heldout_exact'] == result['heldout_cases']
    assert result['source_was_parsed_by_learner'] is False
    assert result['expression']['op'] in {'min', 'max'}
    assert result['trainable_parameter_count'] == 0
