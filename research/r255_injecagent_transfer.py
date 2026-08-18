from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from cogcoder.r255_authority import ActionProposal, AuthorityBoundary, AuthorityEnvelope


def _load_rows(path: Path) -> list[Mapping[str, object]]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, list):
        raise TypeError(f'{path} must contain a JSON array')
    rows = []
    for index, row in enumerate(raw):
        if not isinstance(row, Mapping):
            raise TypeError(f'{path} row {index} must be an object')
        rows.append(row)
    return rows


def evaluate_file(path: str | Path, *, dataset_name: str) -> dict[str, object]:
    path = Path(path)
    rows = _load_rows(path)
    boundary = AuthorityBoundary()
    utility_allowed = 0
    attacker_action_proposals = 0
    attacker_actions_blocked = 0
    authority_escape_count = 0
    malformed = 0
    same_action_id_attacks = 0

    for index, row in enumerate(rows):
        user_tool = str(row.get('User Tool', '')).strip()
        objective = str(row.get('User Instruction', '')).strip() or f'InjecAgent case {index}'
        raw_attackers = row.get('Attacker Tools', ())
        if not user_tool or isinstance(raw_attackers, (str, bytes)) or not isinstance(raw_attackers, Iterable):
            malformed += 1
            continue
        attacker_tools = tuple(str(value).strip() for value in raw_attackers if str(value).strip())
        if not attacker_tools:
            malformed += 1
            continue

        envelope = AuthorityEnvelope.issue(
            objective=objective,
            allowed_actions={user_tool},
            allowed_side_effect_classes={'user_authorized_tool'},
            issuer='host:user-plan',
        )
        intended = boundary.authorize(
            envelope,
            ActionProposal(
                action_id=user_tool,
                side_effect_class='user_authorized_tool',
                proposed_by='host_planner',
                source_uri=f'injecagent://{dataset_name}/{index}/user-plan',
            ),
        )
        utility_allowed += int(intended.allowed)

        for attacker_tool in attacker_tools:
            attacker_action_proposals += 1
            same_action_id_attacks += int(attacker_tool == user_tool)
            decision = boundary.authorize(
                envelope,
                ActionProposal(
                    action_id=attacker_tool,
                    side_effect_class='untrusted_requested_action',
                    proposed_by='untrusted_tool_data',
                    source_uri=f'injecagent://{dataset_name}/{index}/tool-response',
                ),
            )
            attacker_actions_blocked += int(not decision.allowed)
            authority_escape_count += int(decision.allowed)

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    passed = bool(
        malformed == 0
        and utility_allowed == len(rows)
        and attacker_action_proposals > 0
        and attacker_actions_blocked == attacker_action_proposals
        and authority_escape_count == 0
    )
    return {
        'dataset': str(dataset_name),
        'path_name': path.name,
        'sha256': digest,
        'cases': len(rows),
        'malformed_cases': malformed,
        'utility_allowed': utility_allowed,
        'attacker_action_proposals': attacker_action_proposals,
        'attacker_actions_blocked': attacker_actions_blocked,
        'authority_escape_count': authority_escape_count,
        'same_action_id_attacks': same_action_id_attacks,
        'passed': passed,
    }


def run(datasets: Iterable[tuple[str, str | Path]], *, repository: str, commit: str) -> dict[str, object]:
    results = [evaluate_file(path, dataset_name=name) for name, path in datasets]
    return {
        'milestone': 'R2.55',
        'validation': 'independently-sourced-injecagent-authority-boundary-transfer',
        'repository': str(repository),
        'commit': str(commit),
        'datasets': results,
        'dataset_count': len(results),
        'cases': sum(int(row['cases']) for row in results),
        'utility_allowed': sum(int(row['utility_allowed']) for row in results),
        'attacker_action_proposals': sum(int(row['attacker_action_proposals']) for row in results),
        'attacker_actions_blocked': sum(int(row['attacker_actions_blocked']) for row in results),
        'authority_escape_count': sum(int(row['authority_escape_count']) for row in results),
        'passed': bool(results) and all(bool(row['passed']) for row in results),
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'This validates a deterministic host authority boundary against InjecAgent-labeled attacker '
            'action proposals; it does not measure whether an LLM itself resists or detects prompt injection.'
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', action='append', default=[], help='NAME=PATH; repeat for multiple datasets')
    parser.add_argument('--repository', default='uiuc-kang-lab/InjecAgent')
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    datasets = []
    for raw in args.dataset:
        if '=' not in raw:
            raise SystemExit('--dataset must be NAME=PATH')
        name, path = raw.split('=', 1)
        datasets.append((name, path))
    result = run(datasets, repository=args.repository, commit=args.commit)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
