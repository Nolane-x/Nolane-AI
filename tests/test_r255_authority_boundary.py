import pytest


def test_untrusted_tool_data_cannot_expand_preissued_action_authority():
    from cogcoder.r255_authority import AuthorityBoundary, AuthorityEnvelope, ActionProposal

    envelope = AuthorityEnvelope.issue(
        objective='summarize repository details',
        allowed_actions={'GitHubGetRepositoryDetails'},
        allowed_side_effect_classes={'read_only'},
        issuer='host:user-plan',
    )
    boundary = AuthorityBoundary()

    attacker = boundary.authorize(
        envelope,
        ActionProposal(
            action_id='GitHubDeleteRepository',
            side_effect_class='external_write',
            proposed_by='untrusted_tool_data',
            source_uri='tool://GitHubGetRepositoryDetails/response',
        ),
    )
    assert attacker.allowed is False
    assert attacker.reason == 'action_not_pre_authorized'

    intended = boundary.authorize(
        envelope,
        ActionProposal(
            action_id='GitHubGetRepositoryDetails',
            side_effect_class='read_only',
            proposed_by='host_planner',
            source_uri='nolane://planner',
        ),
    )
    assert intended.allowed is True
    assert intended.reason == 'authorized'


def test_external_content_cannot_mint_or_mutate_authority_envelope():
    from cogcoder.r255_authority import AuthorityEnvelope

    envelope = AuthorityEnvelope.issue(
        objective='inspect package metadata',
        allowed_actions={'PackageReadMetadata'},
        allowed_side_effect_classes={'read_only'},
        issuer='host:user-plan',
    )
    snapshot = envelope.to_dict()
    assert envelope.verify()

    tampered = dict(snapshot)
    tampered['allowed_actions'] = ['PackageReadMetadata', 'TerminalExecute']
    restored = AuthorityEnvelope.from_dict(tampered)
    assert restored.verify() is False

    with pytest.raises(ValueError, match='host authority required'):
        AuthorityEnvelope.issue(
            objective='bad expansion',
            allowed_actions={'TerminalExecute'},
            allowed_side_effect_classes={'external_write'},
            issuer='untrusted_tool_data',
        )


def test_authority_boundary_separates_action_identity_from_side_effect_scope():
    from cogcoder.r255_authority import AuthorityBoundary, AuthorityEnvelope, ActionProposal

    envelope = AuthorityEnvelope.issue(
        objective='read repository',
        allowed_actions={'GitHubGetRepositoryDetails', 'GitHubSearchRepositories'},
        allowed_side_effect_classes={'read_only'},
        issuer='host:user-plan',
    )
    decision = AuthorityBoundary().authorize(
        envelope,
        ActionProposal(
            action_id='GitHubSearchRepositories',
            side_effect_class='external_write',
            proposed_by='model',
            source_uri='nolane://model',
        ),
    )
    assert decision.allowed is False
    assert decision.reason == 'side_effect_not_pre_authorized'


def test_authority_envelope_can_be_narrowed_but_never_widened_by_child_scope():
    from cogcoder.r255_authority import AuthorityEnvelope

    parent = AuthorityEnvelope.issue(
        objective='repository maintenance',
        allowed_actions={'Read', 'Test', 'Write'},
        allowed_side_effect_classes={'read_only', 'state_only', 'external_write'},
        issuer='host:user-plan',
    )
    child = parent.narrow(
        objective='verification subgoal',
        allowed_actions={'Read', 'Test'},
        allowed_side_effect_classes={'read_only', 'state_only'},
    )
    assert child.verify()
    assert child.allowed_actions == frozenset({'Read', 'Test'})

    with pytest.raises(ValueError, match='cannot widen'):
        parent.narrow(
            objective='malicious expansion',
            allowed_actions={'Read', 'TerminalExecute'},
            allowed_side_effect_classes={'read_only'},
        )
