from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.context import ContextCompiler
from cogcoder.organization.events import EventLedger
from cogcoder.organization.memory import MemoryFabric
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.scheduler import WakeSleepScheduler
from cogcoder.organization.tasks import TaskGraph
from cogcoder.organization.types import EventKind, MemoryScope


def _stack():
    registry = AgentRegistry(build_first_generation_blueprint())
    ledger = EventLedger()
    memory = MemoryFabric()
    tasks = TaskGraph(ledger=ledger)
    compiler = ContextCompiler(registry=registry, memory=memory, ledger=ledger, tasks=tasks)
    return registry, ledger, memory, tasks, compiler


def test_context_compiler_respects_memory_scopes():
    registry, ledger, memory, tasks, compiler = _stack()
    agent_id = 'coding.backend.01'
    memory.write(MemoryScope.GLOBAL, 'global architecture rule', owner_agent_id='nolane.central')
    memory.write(MemoryScope.REGION, 'coding convention', owner_agent_id='coding.chief', region='core-coding')
    memory.write(MemoryScope.PERSONAL, 'backend learned retry pattern', owner_agent_id=agent_id)
    memory.write(MemoryScope.TASK, 'task acceptance criterion', owner_agent_id='planning.chief', task_id='T-184')
    isolated = memory.write(MemoryScope.PRIVATE, 'isolated debugger note', owner_agent_id='debug.runtime-trace.01')
    tasks.add_task('T-184', title='Add durable job store', plan_node_id='P-41')
    tasks.lease('T-184', agent_id)

    capsule = compiler.compile(agent_id, task_id='T-184')
    texts = {entry.text for entry in capsule.memories}
    assert {'global architecture rule', 'coding convention', 'backend learned retry pattern', 'task acceptance criterion'} <= texts
    assert isolated.text not in texts
    assert capsule.plan_version == tasks.plan_version


def test_sleeping_agent_resumes_with_only_event_delta():
    registry, ledger, memory, tasks, compiler = _stack()
    scheduler = WakeSleepScheduler(registry=registry, ledger=ledger)
    agent_id = 'coding.backend.01'
    first = ledger.append(EventKind.TASK_STARTED, source_agent_id=agent_id, target_agent_id=agent_id, region='core-coding', payload={'task_id': 'T-184'})
    scheduler.sleep(agent_id, checkpoint_event_id=first.event_id)
    amendment = ledger.append(EventKind.PLAN_AMENDED, source_agent_id='planning.chief', target_agent_id=agent_id, region='planning-program', payload={'plan_version': 2, 'affected_tasks': ['T-184']})
    scheduler.notify_event(amendment)
    assert agent_id in scheduler.due_agents()
    scheduler.wake(agent_id, reason='plan-amended')
    capsule = compiler.compile(agent_id, task_id='T-184', since_event_id=first.event_id)
    assert [event.event_id for event in capsule.event_delta] == [amendment.event_id]


def test_memory_promotion_requires_receipt():
    memory = MemoryFabric()
    row = memory.write(MemoryScope.PRIVATE, 'candidate lesson', owner_agent_id='coding.backend.01')
    promoted = memory.promote(row.memory_id, MemoryScope.GLOBAL, promotion_receipt_id='PR-7')
    assert promoted.parent_memory_id == row.memory_id
    assert promoted.promotion_receipt_id == 'PR-7'
