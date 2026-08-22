from cogcoder.organization.runtime import OrganizationRuntime


def test_verification_and_security_context_receive_assurance_state():
    runtime = OrganizationRuntime.first_generation()
    verification = runtime.context.compile('verification.fuzz-regression.01')
    security = runtime.context.compile('security.adversarial.01')
    assert ('assurance-state', runtime.assurance.digest) in verification.authoritative_artifacts
    assert ('assurance-state', runtime.assurance.digest) in security.authoritative_artifacts


def test_unrelated_build_region_does_not_receive_full_private_assurance_state():
    runtime = OrganizationRuntime.first_generation()
    coding = runtime.context.compile('coding.backend.01')
    assert not any(name == 'assurance-state' for name, _ in coding.authoritative_artifacts)
