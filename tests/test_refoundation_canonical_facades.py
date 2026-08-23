from __future__ import annotations


def test_canonical_organization_facades_preserve_class_identity() -> None:
    from cogcoder.organization.authority import AuthorityGraph as OldAuthorityGraph
    from cogcoder.organization.central import CentralControlPlane as OldCentralControlPlane
    from cogcoder.organization.coordination import CoordinationControlPlane as OldCoordinationControlPlane
    from cogcoder.organization.events import EventLedger as OldEventLedger
    from cogcoder.organization.registry import AgentRegistry as OldAgentRegistry
    from cogcoder.organization.runtime import OrganizationRuntime as OldOrganizationRuntime
    from cogcoder.organization.tasks import TaskGraph as OldTaskGraph

    from nolane.organization.authority import AuthorityGraph
    from nolane.organization.central import CentralControlPlane
    from nolane.organization.coordination import CoordinationControlPlane
    from nolane.organization.events import EventLedger
    from nolane.organization.identity import AgentRegistry
    from nolane.organization.runtime import OrganizationRuntime
    from nolane.organization.tasks import TaskGraph

    assert AuthorityGraph is OldAuthorityGraph
    assert CentralControlPlane is OldCentralControlPlane
    assert CoordinationControlPlane is OldCoordinationControlPlane
    assert EventLedger is OldEventLedger
    assert AgentRegistry is OldAgentRegistry
    assert OrganizationRuntime is OldOrganizationRuntime
    assert TaskGraph is OldTaskGraph


def test_canonical_external_core_facades_preserve_class_identity() -> None:
    from cogcoder.organization.architecture import ArchitectureControlPlane as OldArchitecture
    from cogcoder.organization.assurance import AssuranceControlPlane as OldAssurance
    from cogcoder.organization.coding import CodingControlPlane as OldCoding
    from cogcoder.organization.context import ContextCompiler as OldContext
    from cogcoder.organization.debugging import DebugControlPlane as OldDebugging
    from cogcoder.organization.external_core import ExternalCoreRegistry as OldInvokableRegistry
    from cogcoder.organization.integration import IntegrationControlPlane as OldIntegration
    from cogcoder.organization.memory import MemoryFabric as OldMemory
    from cogcoder.organization.operations import OperationsControlPlane as OldOperations
    from cogcoder.organization.planning import PlanningControlPlane as OldPlanning
    from cogcoder.organization.requirements import RequirementsControlPlane as OldRequirements
    from cogcoder.organization.research import ResearchControlPlane as OldResearch
    from cogcoder.organization.ui import UIControlPlane as OldUI
    from cogcoder.organization.execution import OrganizationExecutionControlPlane as OldExecution

    from nolane.external_core.architecture import ArchitectureControlPlane
    from nolane.external_core.assurance import AssuranceControlPlane
    from nolane.external_core.coding import CodingControlPlane
    from nolane.external_core.context import ContextCompiler
    from nolane.external_core.debugging import DebugControlPlane
    from nolane.external_core.execution import OrganizationExecutionControlPlane
    from nolane.external_core.integration import IntegrationControlPlane
    from nolane.external_core.invokable import ExternalCoreRegistry
    from nolane.external_core.memory import MemoryFabric
    from nolane.external_core.operations import OperationsControlPlane
    from nolane.external_core.planning import PlanningControlPlane
    from nolane.external_core.requirements import RequirementsControlPlane
    from nolane.external_core.research import ResearchControlPlane
    from nolane.external_core.ui_ux import UIControlPlane

    assert ArchitectureControlPlane is OldArchitecture
    assert AssuranceControlPlane is OldAssurance
    assert CodingControlPlane is OldCoding
    assert ContextCompiler is OldContext
    assert DebugControlPlane is OldDebugging
    assert ExternalCoreRegistry is OldInvokableRegistry
    assert IntegrationControlPlane is OldIntegration
    assert MemoryFabric is OldMemory
    assert OperationsControlPlane is OldOperations
    assert PlanningControlPlane is OldPlanning
    assert RequirementsControlPlane is OldRequirements
    assert ResearchControlPlane is OldResearch
    assert UIControlPlane is OldUI
    assert OrganizationExecutionControlPlane is OldExecution


def test_canonical_evaluation_facades_preserve_class_identity() -> None:
    from cogcoder.organization.campaign import EvaluationCampaignControlPlane as OldCampaign
    from cogcoder.organization.evaluation import EvaluationScalingControlPlane as OldEvaluation

    from nolane.evaluation.campaign import EvaluationCampaignControlPlane
    from nolane.evaluation.scaling import EvaluationScalingControlPlane

    assert EvaluationCampaignControlPlane is OldCampaign
    assert EvaluationScalingControlPlane is OldEvaluation


def test_canonical_neural_boundary_keeps_checkpoint_authority_in_old_bridge() -> None:
    from cogcoder.organization.execution_inference import R23InferenceBackend as OldAdapter
    from nolane.neural.inference_bridge import R23InferenceBackend

    assert R23InferenceBackend is OldAdapter


def test_every_facade_declares_independent_component_version_and_source() -> None:
    import nolane.evaluation.scaling as evaluation_scaling
    import nolane.external_core.memory as memory
    import nolane.external_core.execution as execution
    import nolane.organization.runtime as runtime

    for module in (evaluation_scaling, memory, execution, runtime):
        assert module.COMPONENT_VERSION == "0.0.0"
        assert module.MIGRATED_FROM.startswith("cogcoder.organization.")
