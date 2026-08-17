from __future__ import annotations

from dataclasses import dataclass


_ALLOWED_STATUS = {'implemented', 'host_required', 'knowledge_only', 'experimental'}


@dataclass(frozen=True, slots=True)
class SubOperatorDescriptor:
    operator_id: str
    status: str
    summary: str
    tags: frozenset[str]

    def __post_init__(self) -> None:
        if not self.operator_id or '.' not in self.operator_id:
            raise ValueError('operator_id must be namespaced')
        if self.status not in _ALLOWED_STATUS:
            raise ValueError(f'unknown status: {self.status}')
        if not self.summary.strip():
            raise ValueError('summary must be non-empty')
        if not self.tags:
            raise ValueError('tags must be non-empty')


@dataclass(frozen=True, slots=True)
class OperatorFamilyDescriptor:
    family_id: str
    summary: str
    suboperators: tuple[SubOperatorDescriptor, ...]

    def __post_init__(self) -> None:
        if not self.family_id or not self.summary.strip():
            raise ValueError('family identity must be non-empty')
        if not self.suboperators:
            raise ValueError('family must contain suboperators')
        if any(not row.operator_id.startswith(self.family_id + '.') for row in self.suboperators):
            raise ValueError('suboperator namespace mismatch')


def _family(family_id: str, summary: str, rows: tuple[tuple[str, str, str, tuple[str, ...]], ...]) -> OperatorFamilyDescriptor:
    return OperatorFamilyDescriptor(
        family_id,
        summary,
        tuple(
            SubOperatorDescriptor(
                f'{family_id}.{name}',
                status,
                description,
                frozenset(tags),
            )
            for name, status, description, tags in rows
        ),
    )


def _rows(*items: tuple[str, str, str, tuple[str, ...]]):
    return tuple(items)


def build_default_externalization_catalog() -> tuple[OperatorFamilyDescriptor, ...]:
    """Return a broad, explicit catalog of cognition that can live outside model weights.

    `implemented` means Nolane already has a concrete zero-parameter mechanism that substantially
    overlaps the operator. Other statuses are intentionally explicit so the catalog never becomes
    a capability claim merely by listing a behavior.
    """
    families = (
        _family('factual_knowledge', 'Acquire, version, reconcile, and compact non-parametric factual evidence.', _rows(
            ('retrieve_fact','implemented','Retrieve evidence relevant to a concrete factual gap.',('retrieval','fact')),
            ('retrieve_api_docs','implemented','Retrieve API or interface documentation at cognition time.',('retrieval','api')),
            ('multi_hop_retrieve','implemented','Issue follow-up retrieval after an intermediate entity is discovered.',('retrieval','multi-hop')),
            ('cross_source_compare','implemented','Compare independent evidence sources instead of trusting one hit.',('evidence','compare')),
            ('resolve_conflicting_claims','implemented','Retain contradictions and rank current alternatives by evidence.',('conflict','belief')),
            ('temporal_filter','experimental','Select evidence valid for the required time/version.',('version','time')),
            ('provenance_verify','implemented','Verify source/content provenance before evidence can be trusted.',('provenance','integrity')),
            ('query_expand','implemented','Refine a retrieval query using newly discovered anchors.',('query','retrieval')),
            ('evidence_compact','implemented','Build a bounded high-value working evidence set.',('compression','evidence')),
        )),
        _family('episodic_memory', 'Store and retrieve prior trajectories, decisions, failures, and outcomes.', _rows(
            ('recall_similar_episode','experimental','Retrieve prior episodes with similar objectives and context.',('episode','retrieval')),
            ('recall_prior_failure','experimental','Retrieve previous failed attempts and their failure reasons.',('episode','failure')),
            ('recall_prior_fix','experimental','Retrieve previously validated fixes for analogous situations.',('episode','repair')),
            ('recall_decision_rationale','knowledge_only','Retrieve the recorded evidence behind an earlier decision.',('episode','decision')),
            ('episode_checkpoint','experimental','Persist a compact public-state checkpoint for later resumption.',('episode','checkpoint')),
            ('episode_consolidate','experimental','Compress repeated episodes into reusable patterns.',('episode','consolidation')),
            ('episode_version','experimental','Version episodes when environment or policy changes.',('episode','version')),
            ('episode_retire','experimental','Retire misleading or superseded episodes without deleting provenance.',('episode','retire')),
        )),
        _family('working_memory', 'Maintain structured external state without forcing every intermediate into model context.', _rows(
            ('pin_evidence','experimental','Pin high-value evidence so compaction cannot evict it.',('working-memory','evidence')),
            ('goal_stack','experimental','Maintain current objective and nested subgoals.',('working-memory','goal')),
            ('hypothesis_board','experimental','Maintain competing hypotheses and evidence links.',('working-memory','hypothesis')),
            ('dependency_board','experimental','Maintain dependencies among subgoals or claims.',('working-memory','dependency')),
            ('conflict_buffer','experimental','Surface unresolved contradictions as first-class state.',('working-memory','conflict')),
            ('state_compact','experimental','Compress public reasoning state under a context budget.',('working-memory','compression')),
            ('checkpoint_restore','experimental','Restore an external state checkpoint after a failed branch.',('working-memory','restore')),
            ('attention_window','experimental','Select which external state slices enter the next model call.',('working-memory','attention')),
        )),
        _family('planning', 'Construct, validate, execute, and revise structured plans outside the model.', _rows(
            ('decompose_goal','host_required','Split an objective into independently verifiable subgoals.',('plan','decompose')),
            ('backward_plan','host_required','Plan backward from desired postconditions to prerequisites.',('plan','backward')),
            ('forward_plan','host_required','Plan forward from available capabilities and state.',('plan','forward')),
            ('dependency_toposort','implemented','Order steps from an explicit dependency graph.',('plan','dependency')),
            ('critical_path','host_required','Identify bottleneck subgoals that dominate completion.',('plan','critical-path')),
            ('contingency_plan','host_required','Precompute fallback branches for likely failures.',('plan','contingency')),
            ('replan_after_failure','experimental','Revise a plan when an assumption or step is falsified.',('plan','replan')),
            ('milestone_gate','implemented','Require evidence before advancing to a later milestone.',('plan','gate')),
            ('resource_allocate','experimental','Allocate compute/tool/test budget across plan branches.',('plan','resource')),
        )),
        _family('search', 'Explore alternative solutions with explicit external algorithms.', _rows(
            ('beam_search','host_required','Maintain a bounded beam of high-value candidate states.',('search','beam')),
            ('best_first','host_required','Expand candidates by a priority/heuristic score.',('search','best-first')),
            ('mcts','host_required','Use Monte Carlo tree search for lookahead under uncertainty.',('search','mcts')),
            ('evolutionary_search','host_required','Mutate and select candidate solutions over generations.',('search','evolution')),
            ('program_synthesis','implemented','Search a bounded program/operator language for a satisfying candidate.',('search','synthesis')),
            ('cegis','implemented','Alternate candidate generation with counterexample acquisition.',('search','counterexample')),
            ('branch_and_bound','host_required','Prune search branches using admissible bounds.',('search','bound')),
            ('diversify_frontier','experimental','Penalize near-duplicate branches to escape stagnation.',('search','diversity')),
            ('deduplicate_semantics','implemented','Collapse semantically equivalent candidates while preserving needed aliases.',('search','dedupe')),
        )),
        _family('verification', 'Delegate correctness judgments to explicit external checkers.', _rows(
            ('run_unit_tests','host_required','Execute focused unit tests against a candidate.',('verify','test')),
            ('run_property_tests','host_required','Generate/check properties rather than only examples.',('verify','property')),
            ('type_check','host_required','Use a static type checker as an independent verifier.',('verify','type')),
            ('compile_check','implemented','Compile generated code/programs before accepting them.',('verify','compiler')),
            ('static_analysis','host_required','Invoke static analysis for structural or safety invariants.',('verify','static')),
            ('theorem_prove','host_required','Use a theorem prover for formal obligations.',('verify','proof')),
            ('differential_test','host_required','Compare independent implementations or versions.',('verify','differential')),
            ('invariant_check','implemented','Check explicit invariants at milestone boundaries.',('verify','invariant')),
            ('full_exhaustive_check','implemented','Exhaustively certify bounded finite domains after sparse search.',('verify','exhaustive')),
        )),
        _family('world_model', 'Represent and simulate environment state transitions outside latent activations.', _rows(
            ('state_transition','host_required','Apply an explicit transition model to a world state.',('world','transition')),
            ('rollout','host_required','Simulate multiple future steps under a candidate policy.',('world','rollout')),
            ('counterfactual_rollout','host_required','Simulate a changed action while holding other factors fixed.',('world','counterfactual')),
            ('impact_analysis','implemented','Propagate a proposed edit through a repository dependency graph.',('world','impact')),
            ('scenario_compare','host_required','Compare outcomes under alternative interventions.',('world','scenario')),
            ('uncertainty_propagate','experimental','Propagate state uncertainty through a model.',('world','uncertainty')),
            ('state_snapshot','implemented','Create an immutable bounded environment/repository snapshot.',('world','snapshot')),
            ('model_calibrate','experimental','Calibrate a world model against observed transitions.',('world','calibration')),
        )),
        _family('tool_knowledge', 'Discover tools and retrieve usage contracts instead of memorizing them in weights.', _rows(
            ('discover_tool','experimental','Find a tool whose capabilities match a missing operation.',('tool','discovery')),
            ('retrieve_schema','host_required','Retrieve the tool input/output schema at runtime.',('tool','schema')),
            ('retrieve_examples','knowledge_only','Retrieve validated usage examples for a selected tool.',('tool','example')),
            ('permission_check','host_required','Check tool permissions and side-effect boundaries before use.',('tool','permission')),
            ('dry_run','host_required','Validate a tool call without committing irreversible side effects.',('tool','dry-run')),
            ('fallback_tool','experimental','Route to an alternate tool after a failure.',('tool','fallback')),
            ('tool_health_check','host_required','Verify that a tool/connector is currently functional.',('tool','health')),
            ('tool_version_align','knowledge_only','Select instructions compatible with the active tool version.',('tool','version')),
        )),
        _family('skill_library', 'Store, retrieve, compose, validate, and retire procedures outside weights.', _rows(
            ('retrieve_skill','implemented','Retrieve a validated skill artifact from a registry.',('skill','retrieval')),
            ('compose_skills','implemented','Compose multiple external skill programs.',('skill','composition')),
            ('validate_skill','implemented','Validate a skill before promoting it as current.',('skill','validation')),
            ('version_skill','implemented','Maintain multiple provenance-bound skill versions.',('skill','version')),
            ('adapt_skill','experimental','Adapt a skill to a new context under verification.',('skill','adapt')),
            ('retire_skill','implemented','Retire low-value or capacity-expensive skills.',('skill','retire')),
            ('rollback_skill','implemented','Restore a prior validated skill version after regression.',('skill','rollback')),
            ('skill_ablation','experimental','Measure whether a skill causally improves outcomes.',('skill','ablation')),
        )),
        _family('representation', 'Build and switch explicit representations rather than keeping structure only in hidden states.', _rows(
            ('build_ast','implemented','Parse code into an abstract syntax tree.',('representation','ast')),
            ('build_cfg','host_required','Construct a control-flow graph.',('representation','cfg')),
            ('build_dataflow','implemented','Construct def-use/value-flow relations.',('representation','dataflow')),
            ('build_call_graph','implemented','Construct static caller/callee relationships.',('representation','call-graph')),
            ('build_dependency_graph','implemented','Construct repository/module dependency relationships.',('representation','dependency')),
            ('build_knowledge_graph','host_required','Represent entities/relations as a graph.',('representation','knowledge-graph')),
            ('switch_representation','experimental','Change representation when the current one cannot separate hypotheses.',('representation','switch')),
            ('align_representations','experimental','Map evidence between multiple simultaneous representations.',('representation','align')),
            ('invent_relational_query','implemented','Induce a relational query from positive/negative structural examples.',('representation','induction')),
        )),
        _family('uncertainty_tracking', 'Track uncertainty, alternatives, and competence explicitly.', _rows(
            ('posterior_update','implemented','Update hypothesis probability from verifier evidence.',('uncertainty','posterior')),
            ('entropy_measure','implemented','Measure uncertainty over competing hypotheses.',('uncertainty','entropy')),
            ('confidence_calibrate','experimental','Calibrate confidence against historical correctness.',('uncertainty','calibration')),
            ('ensemble_disagreement','host_required','Use solver disagreement as uncertainty evidence.',('uncertainty','ensemble')),
            ('evidence_balance','implemented','Track support and conflict among evidence sources.',('uncertainty','evidence')),
            ('unknown_unknown_probe','experimental','Actively seek evidence that could falsify current assumptions.',('uncertainty','unknown')),
            ('capability_confidence','experimental','Estimate competence for a task/operator context.',('uncertainty','capability')),
            ('uncertainty_budget','experimental','Spend verification/retrieval budget based on uncertainty.',('uncertainty','budget')),
        )),
        _family('information_acquisition', 'Choose what observation, query, test, or question is worth acquiring next.', _rows(
            ('value_of_information','implemented','Score probes by expected information gain.',('acquire','voi')),
            ('active_retrieve','implemented','Retrieve only when uncertainty/query drift warrants it.',('acquire','retrieval')),
            ('ask_user','host_required','Request missing information from a human.',('acquire','question')),
            ('run_discriminating_test','implemented','Choose a test that separates competing hypotheses.',('acquire','test')),
            ('inspect_source','host_required','Read the minimal source region needed to resolve a gap.',('acquire','source')),
            ('instrument_runtime','host_required','Collect runtime traces for an unresolved behavior.',('acquire','instrument')),
            ('experiment_design','experimental','Construct an intervention with high expected information gain.',('acquire','experiment')),
            ('stop_acquisition','implemented','Stop when no novel evidence or budget remains.',('acquire','stop')),
        )),
        _family('counterexample_memory', 'Persist falsifiers so the system does not repeatedly revisit disproven routes.', _rows(
            ('store_counterexample','implemented','Store a falsifying case with provenance/context.',('counterexample','store')),
            ('retrieve_counterexample','experimental','Retrieve falsifiers relevant to a current hypothesis.',('counterexample','retrieve')),
            ('cluster_counterexamples','experimental','Group failures by common mechanism.',('counterexample','cluster')),
            ('generalize_counterexample','experimental','Extract a broader forbidden condition from repeated failures.',('counterexample','generalize')),
            ('ban_exact_route','implemented','Prevent reusing an exact procedure/context pair already falsified.',('counterexample','ban')),
            ('near_miss_lookup','experimental','Retrieve structurally similar failures before retrying.',('counterexample','similarity')),
            ('counterexample_replay','implemented','Re-run stored falsifiers against a revised candidate.',('counterexample','replay')),
            ('counterexample_expire','experimental','Retire falsifiers invalidated by environment/version changes.',('counterexample','version')),
        )),
        _family('credit_assignment', 'Attribute success/failure to external operators, steps, and representations.', _rows(
            ('operator_credit','implemented','Update success/failure statistics for a procedure/operator context.',('credit','operator')),
            ('step_ablation','experimental','Remove one step to estimate its causal contribution.',('credit','ablation')),
            ('failure_localize','experimental','Locate the earliest step whose output violates an invariant.',('credit','failure')),
            ('representation_credit','experimental','Track which representation enabled a successful decision.',('credit','representation')),
            ('tool_credit','experimental','Track tool reliability by task context.',('credit','tool')),
            ('skill_credit','implemented','Update skill competence from observed outcomes.',('credit','skill')),
            ('evidence_credit','experimental','Estimate which evidence changed a decision.',('credit','evidence')),
            ('delayed_credit','experimental','Propagate later verifier outcomes to earlier operator choices.',('credit','temporal')),
        )),
        _family('self_improvement', 'Turn failures and successes into new external artifacts without assuming weight updates.', _rows(
            ('mine_failures','experimental','Collect recurring failure signatures from receipts.',('improve','failure')),
            ('generate_benchmark','experimental','Turn validated failures into regression tasks.',('improve','benchmark')),
            ('distill_procedure','experimental','Compress a successful trajectory into a reusable procedure card.',('improve','distill')),
            ('tune_router','experimental','Update external routing priors from credit statistics.',('improve','router')),
            ('promote_operator','experimental','Promote a trial operator after verified success.',('improve','promote')),
            ('quarantine_operator','implemented','Quarantine an operator after a causal regression/falsifier.',('improve','quarantine')),
            ('retrain_small_module','host_required','Retrain a bounded learned component with frozen evaluation.',('improve','train')),
            ('rollback_improvement','implemented','Restore a previously accepted external state after regression.',('improve','rollback')),
        )),
        _family('attention_routing', 'Route cognition among models, tools, memories, representations, and evidence.', _rows(
            ('route_operator','experimental','Select an external procedure for the current deficit.',('route','operator')),
            ('route_tool','host_required','Select a tool by capability, cost, and risk.',('route','tool')),
            ('route_memory','experimental','Select episodic/semantic/counterexample memory sources.',('route','memory')),
            ('route_representation','experimental','Select a representation appropriate to the task stage.',('route','representation')),
            ('route_model','host_required','Select a model/solver by capability boundary.',('route','model')),
            ('budget_route','experimental','Route under compute/token/tool-call budgets.',('route','budget')),
            ('risk_route','experimental','Prefer safer operators for high-impact actions.',('route','risk')),
            ('fallback_route','experimental','Choose a recovery route after an operator failure.',('route','fallback')),
        )),
        _family('multi_agent_cognition', 'Coordinate independent solvers and critics outside a single model.', _rows(
            ('delegate_specialist','host_required','Delegate a subproblem to a specialist solver.',('agent','delegate')),
            ('parallel_solve','host_required','Run independent solvers on separable branches.',('agent','parallel')),
            ('adversarial_critic','host_required','Assign a challenger to falsify a candidate.',('agent','critic')),
            ('debate','host_required','Exchange structured arguments between solvers.',('agent','debate')),
            ('judge','host_required','Select among candidate solutions using explicit evidence.',('agent','judge')),
            ('consensus','host_required','Aggregate compatible independent conclusions.',('agent','consensus')),
            ('diversity_enforce','experimental','Penalize redundant agents/solutions.',('agent','diversity')),
            ('cross_agent_memory','experimental','Share validated artifacts without sharing private scratchpads.',('agent','memory')),
        )),
        _family('temporal_reasoning', 'Reason explicitly about event order, version validity, and changing truth.', _rows(
            ('build_timeline','experimental','Construct an ordered event/version timeline.',('time','timeline')),
            ('select_version','implemented','Select a latest/current record per source/version semantics.',('time','version')),
            ('detect_stale_evidence','experimental','Flag evidence whose validity window is outdated.',('time','stale')),
            ('event_order','experimental','Infer or verify ordering constraints between events.',('time','order')),
            ('state_diff','implemented','Compare repository/system snapshots across versions.',('time','diff')),
            ('temporal_join','experimental','Join facts valid at compatible times.',('time','join')),
            ('expiry_check','experimental','Check whether a cached fact/tool schema has expired.',('time','expiry')),
            ('temporal_counterfactual','host_required','Ask what would hold under a different historical intervention.',('time','counterfactual')),
        )),
        _family('causal_reasoning', 'Trace dependencies and test interventions rather than relying on correlation.', _rows(
            ('dependency_trace','implemented','Trace explicit dependency/value-flow paths.',('causal','trace')),
            ('root_cause','experimental','Rank candidate causes of an observed failure.',('causal','root')),
            ('intervention_test','implemented','Change one factor and observe whether outcome changes.',('causal','intervention')),
            ('counterfactual_compare','host_required','Compare actual and counterfactual outcomes.',('causal','counterfactual')),
            ('mediation_trace','experimental','Identify intermediate nodes carrying an effect.',('causal','mediation')),
            ('causal_graph_build','host_required','Construct a causal graph from domain evidence.',('causal','graph')),
            ('confounder_probe','experimental','Seek evidence for hidden common causes.',('causal','confounder')),
            ('invariance_test','implemented','Test whether a learned relation survives environment changes.',('causal','invariance')),
        )),
        _family('mathematical_reasoning', 'Delegate exact computation and formal constraints to external solvers.', _rows(
            ('symbolic_algebra','host_required','Use a CAS for symbolic simplification/manipulation.',('math','cas')),
            ('sat_solve','host_required','Solve propositional constraints with SAT.',('math','sat')),
            ('smt_solve','host_required','Solve typed arithmetic/logical constraints with SMT.',('math','smt')),
            ('numerical_solve','host_required','Use numerical methods for continuous equations.',('math','numeric')),
            ('optimize','host_required','Use an optimization solver for bounded objectives.',('math','optimize')),
            ('proof_check','host_required','Check a formal derivation.',('math','proof')),
            ('dimensional_check','experimental','Verify unit/dimension consistency.',('math','dimension')),
            ('enumerate_finite_domain','implemented','Exhaustively evaluate a bounded finite domain.',('math','enumerate')),
        )),
        _family('code_reasoning', 'Use explicit program analyses, transformations, execution, and test generation.', _rows(
            ('ast_transform','implemented','Apply typed AST transformations.',('code','ast')),
            ('symbolic_execute','host_required','Symbolically execute paths under constraints.',('code','symbolic')),
            ('taint_analysis','host_required','Trace untrusted/sensitive data flows.',('code','taint')),
            ('dataflow_analysis','implemented','Build/use def-use and value-flow relations.',('code','dataflow')),
            ('call_graph_analysis','implemented','Trace static call relationships across functions/modules.',('code','callgraph')),
            ('test_generate','experimental','Generate discriminating or boundary tests.',('code','testgen')),
            ('fuzz','host_required','Fuzz inputs to discover failures.',('code','fuzz')),
            ('compile_execute','implemented','Compile and execute candidate programs in a bounded runtime.',('code','execute')),
            ('diff_inspect','host_required','Inspect patch diff for unintended changes.',('code','diff')),
            ('bisect','host_required','Binary-search version history for a regression.',('code','bisect')),
        )),
        _family('metacognition', 'Monitor the quality and fit of the current cognitive process itself.', _rows(
            ('detect_stagnation','experimental','Detect repeated actions with no measurable progress.',('meta','stagnation')),
            ('detect_strategy_failure','experimental','Detect repeated verifier failure under one strategy.',('meta','strategy')),
            ('detect_knowledge_gap','experimental','Detect unresolved requirements with insufficient evidence.',('meta','knowledge-gap')),
            ('detect_representation_mismatch','experimental','Detect when a representation cannot discriminate candidates.',('meta','representation')),
            ('switch_strategy','experimental','Route to a different external procedure after stagnation.',('meta','switch')),
            ('self_check_confidence','experimental','Compare self-confidence with objective outcome history.',('meta','confidence')),
            ('request_behavioral_knowledge','experimental','Retrieve how-to knowledge for a missing reasoning behavior.',('meta','procedure')),
            ('stop_or_continue','experimental','Decide whether additional thought has positive expected value.',('meta','stop')),
            ('capability_boundary_check','experimental','Ask whether this solver is competent for the current task.',('meta','capability')),
        )),
        _family('goal_utility', 'Represent goals, preferences, priorities, and trade-offs explicitly.', _rows(
            ('normalize_goal','experimental','Convert an ambiguous request into explicit success criteria.',('goal','normalize')),
            ('prioritize_goals','experimental','Rank competing objectives.',('goal','priority')),
            ('utility_estimate','experimental','Estimate expected utility of candidate outcomes.',('goal','utility')),
            ('tradeoff_analyze','host_required','Compare incompatible objectives under explicit weights.',('goal','tradeoff')),
            ('goal_dependency','experimental','Represent prerequisite relationships among goals.',('goal','dependency')),
            ('goal_progress','experimental','Measure objective progress independently of confidence.',('goal','progress')),
            ('goal_revision','experimental','Revise a goal when new constraints invalidate it.',('goal','revision')),
            ('goal_satisfaction_check','implemented','Check explicit acceptance criteria before finish.',('goal','verify')),
        )),
        _family('constraint_invariants', 'Keep hard constraints and invariants outside model memory and enforce them continuously.', _rows(
            ('register_constraint','experimental','Register a hard or soft constraint with provenance.',('constraint','register')),
            ('propagate_constraint','host_required','Propagate constraints through a structured state.',('constraint','propagate')),
            ('detect_violation','implemented','Detect explicit invariant violations.',('constraint','violation')),
            ('repair_violation','experimental','Route to a repair operator after a violation.',('constraint','repair')),
            ('constraint_prioritize','experimental','Resolve conflicts among soft constraints.',('constraint','priority')),
            ('precondition_check','implemented','Check operator preconditions before execution.',('constraint','precondition')),
            ('postcondition_check','implemented','Check operator expected outputs after execution.',('constraint','postcondition')),
            ('constraint_version','experimental','Version constraints as environments evolve.',('constraint','version')),
        )),
        _family('resource_management', 'Manage compute, token, tool-call, memory, and wall-clock budgets.', _rows(
            ('budget_track','experimental','Track resource consumption by operator/branch.',('resource','track')),
            ('allocate_compute','experimental','Allocate compute across competing branches.',('resource','compute')),
            ('allocate_context','experimental','Allocate context space among evidence/state slices.',('resource','context')),
            ('early_stop_expensive_branch','experimental','Stop a low-value branch before budget exhaustion.',('resource','stop')),
            ('cost_forecast','experimental','Estimate remaining cost before starting a procedure.',('resource','forecast')),
            ('degrade_gracefully','experimental','Switch to cheaper operators under pressure.',('resource','degrade')),
            ('reserve_verification_budget','experimental','Reserve resources for final independent verification.',('resource','verify')),
            ('resource_receipt','experimental','Record actual resource usage for later credit/routing.',('resource','receipt')),
        )),
        _family('observation_normalization', 'Turn raw environment outputs into stable structured evidence.', _rows(
            ('parse_observation','host_required','Parse raw tool/environment output into structured fields.',('observe','parse')),
            ('dedupe_observation','implemented','Deduplicate identical evidence records.',('observe','dedupe')),
            ('normalize_error','experimental','Normalize heterogeneous errors into failure categories.',('observe','error')),
            ('extract_signal','host_required','Extract task-relevant signals from noisy observations.',('observe','signal')),
            ('bind_provenance','implemented','Attach source/version/hash provenance to evidence.',('observe','provenance')),
            ('detect_missing_fields','experimental','Detect required observation fields that were absent.',('observe','missing')),
            ('observation_conflict','implemented','Detect contradictory observations.',('observe','conflict')),
            ('observation_quality','experimental','Estimate reliability/quality of an observation.',('observe','quality')),
        )),
        _family('action_control', 'Execute, gate, monitor, and cancel environment-changing actions.', _rows(
            ('preflight_action','host_required','Check permissions/preconditions before side effects.',('action','preflight')),
            ('execute_action','host_required','Execute a typed environment action.',('action','execute')),
            ('dry_run_action','host_required','Simulate an action when supported.',('action','dry-run')),
            ('monitor_action','host_required','Observe progress/outcome of an action.',('action','monitor')),
            ('cancel_action','host_required','Cancel a still-running reversible action.',('action','cancel')),
            ('confirm_postcondition','implemented','Check expected state after an action.',('action','postcondition')),
            ('compensate_action','host_required','Apply a compensating action after partial failure.',('action','compensate')),
            ('action_receipt','experimental','Persist a provenance-bound action receipt.',('action','receipt')),
        )),
        _family('communication_clarification', 'Externalize when and how the system asks for or conveys missing information.', _rows(
            ('detect_ambiguity','experimental','Detect multiple materially different interpretations.',('communication','ambiguity')),
            ('ask_minimal_question','host_required','Ask the smallest question that resolves a blocker.',('communication','question')),
            ('request_permission','host_required','Request authorization for a consequential action.',('communication','permission')),
            ('summarize_state','host_required','Expose a compact public state summary.',('communication','summary')),
            ('explain_evidence','host_required','Provide evidence/provenance supporting a decision.',('communication','evidence')),
            ('handoff_context','experimental','Package state for another agent/tool without private scratchpad.',('communication','handoff')),
            ('detect_misunderstanding','experimental','Detect user/agent feedback inconsistent with current interpretation.',('communication','repair')),
            ('negotiate_constraints','host_required','Resolve conflicting stakeholder constraints.',('communication','negotiate')),
        )),
        _family('analogical_transfer', 'Retrieve and adapt structurally similar solutions across domains.', _rows(
            ('retrieve_analogy','experimental','Find a prior problem with matching mechanism.',('analogy','retrieve')),
            ('map_structure','host_required','Map roles/relations from source to target.',('analogy','map')),
            ('transfer_operator','experimental','Reuse a validated operator under a new representation.',('analogy','operator')),
            ('adapt_solution','host_required','Adapt a source solution to target constraints.',('analogy','adapt')),
            ('verify_analogy','experimental','Test whether transferred assumptions hold.',('analogy','verify')),
            ('reject_surface_analogy','experimental','Reject analogies based only on superficial lexical overlap.',('analogy','reject')),
            ('cross_domain_score','implemented','Score mechanism overlap across domains.',('analogy','score')),
            ('analogy_counterexample','experimental','Seek a case where the proposed analogy breaks.',('analogy','counterexample')),
        )),
        _family('abstraction_formation', 'Create, promote, and test reusable abstractions outside weights.', _rows(
            ('anti_unify','experimental','Extract common structure across examples.',('abstraction','anti-unify')),
            ('promote_macro','implemented','Promote repeated compositions into reusable macros.',('abstraction','macro')),
            ('compose_abstraction','implemented','Compose existing abstractions recursively.',('abstraction','compose')),
            ('measure_novelty','implemented','Measure whether a composition adds conditional information.',('abstraction','novelty')),
            ('test_abstraction','implemented','Evaluate an abstraction on heldout examples.',('abstraction','test')),
            ('specialize_abstraction','experimental','Restrict an abstraction to a context predicate.',('abstraction','specialize')),
            ('generalize_abstraction','experimental','Remove unnecessary conditions while retaining validity.',('abstraction','generalize')),
            ('retire_abstraction','implemented','Quarantine/retire abstractions after semantic shift.',('abstraction','retire')),
        )),
        _family('hypothesis_generation', 'Generate and manage candidate explanations rather than committing to one story.', _rows(
            ('abduce_causes','host_required','Generate plausible causes for an observation.',('hypothesis','abduction')),
            ('generate_alternatives','host_required','Generate diverse candidate explanations/solutions.',('hypothesis','diversity')),
            ('rank_prior','experimental','Assign structured priors to hypotheses.',('hypothesis','prior')),
            ('derive_predictions','implemented','Derive predicted labels/outcomes from a candidate operator.',('hypothesis','prediction')),
            ('merge_hypotheses','experimental','Merge compatible hypotheses into a broader one.',('hypothesis','merge')),
            ('split_hypothesis','experimental','Split a vague hypothesis into testable variants.',('hypothesis','split')),
            ('falsify_hypothesis','implemented','Seek or apply counterexamples.',('hypothesis','falsify')),
            ('hypothesis_archive','experimental','Archive rejected hypotheses with reasons.',('hypothesis','archive')),
        )),
        _family('counterfactual_reasoning', 'Represent “what if” alternatives as explicit interventions.', _rows(
            ('define_intervention','host_required','Specify which variable/action changes in a counterfactual.',('counterfactual','intervention')),
            ('hold_fixed','experimental','Specify variables assumed invariant under intervention.',('counterfactual','invariant')),
            ('simulate_alternative','host_required','Simulate the intervened state.',('counterfactual','simulate')),
            ('compare_outcomes','host_required','Compare factual and counterfactual outcomes.',('counterfactual','compare')),
            ('minimal_change','experimental','Find the smallest intervention that changes the outcome.',('counterfactual','minimal')),
            ('necessity_test','experimental','Test whether a factor was necessary for an outcome.',('counterfactual','necessity')),
            ('sufficiency_test','experimental','Test whether a factor is sufficient for an outcome.',('counterfactual','sufficiency')),
            ('counterfactual_verify','host_required','Verify counterfactual predictions against a simulator or experiment.',('counterfactual','verify')),
        )),
        _family('consolidation_forgetting', 'Compress long-lived experience while retaining provenance and falsifiers.', _rows(
            ('summarize_episode','experimental','Compress a completed episode into durable public facts/receipts.',('consolidate','episode')),
            ('distill_pattern','experimental','Extract recurring procedure patterns from episodes.',('consolidate','pattern')),
            ('merge_duplicate_memory','experimental','Merge semantically duplicate artifacts.',('consolidate','dedupe')),
            ('retain_counterexample','implemented','Protect falsifiers from lossy forgetting.',('consolidate','counterexample')),
            ('retire_stale_memory','experimental','Retire memories made obsolete by version changes.',('consolidate','stale')),
            ('compress_evidence','implemented','Keep a bounded high-value evidence working set.',('consolidate','evidence')),
            ('memory_decay','experimental','Reduce routing weight for unused low-value artifacts.',('consolidate','decay')),
            ('memory_audit','experimental','Verify retained memory still has valid provenance.',('consolidate','audit')),
        )),
        _family('curiosity_exploration', 'Allocate exploration toward novelty, uncertainty, and capability growth.', _rows(
            ('novelty_detect','experimental','Detect states unlike prior experience.',('curiosity','novelty')),
            ('frontier_select','experimental','Select an unexplored but valuable capability frontier.',('curiosity','frontier')),
            ('uncertainty_explore','experimental','Explore where belief uncertainty is high.',('curiosity','uncertainty')),
            ('capability_gap_explore','experimental','Explore tasks just outside current competence.',('curiosity','capability')),
            ('diversity_bonus','experimental','Reward non-redundant exploration.',('curiosity','diversity')),
            ('safe_experiment','host_required','Run bounded experiments with controlled side effects.',('curiosity','experiment')),
            ('exploration_budget','experimental','Bound curiosity by cost/risk.',('curiosity','budget')),
            ('archive_discovery','experimental','Store verified novel findings for future routing.',('curiosity','archive')),
        )),
        _family('identity_provenance', 'Bind artifacts, observations, and procedures to stable identity and lineage.', _rows(
            ('content_hash','implemented','Hash content to detect tampering.',('identity','hash')),
            ('source_bind','implemented','Bind evidence to source URI and version.',('identity','source')),
            ('lineage_record','implemented','Record artifact/procedure provenance lineage.',('identity','lineage')),
            ('version_identity','implemented','Maintain stable identity across versions.',('identity','version')),
            ('collision_detect','implemented','Reject same identity with conflicting content.',('identity','collision')),
            ('signature_verify','host_required','Verify cryptographic signatures when available.',('identity','signature')),
            ('trust_score','experimental','Maintain source/procedure trust distinct from relevance.',('identity','trust')),
            ('audit_trail','implemented','Preserve receipts needed to reproduce decisions.',('identity','audit')),
        )),
        _family('recovery_rollback', 'Recover safely from failed cognition, tools, patches, and learned artifacts.', _rows(
            ('checkpoint','experimental','Create a recoverable state checkpoint.',('recovery','checkpoint')),
            ('rollback_state','experimental','Restore an earlier external state.',('recovery','state')),
            ('rollback_skill','implemented','Restore a previous validated skill version.',('recovery','skill')),
            ('rollback_patch','host_required','Restore repository/filesystem state after a failed patch.',('recovery','patch')),
            ('compensating_transaction','host_required','Apply compensating operations after partial side effects.',('recovery','transaction')),
            ('failure_isolate','experimental','Quarantine only the failing component/branch.',('recovery','isolate')),
            ('resume_from_checkpoint','experimental','Resume cognition from a known-good checkpoint.',('recovery','resume')),
            ('recovery_verify','implemented','Re-run gates after rollback/recovery.',('recovery','verify')),
        )),
        _family('stopping_termination', 'Decide when a solution is sufficiently verified or further cognition is wasteful.', _rows(
            ('success_gate','implemented','Stop only when explicit acceptance criteria pass.',('stop','success')),
            ('budget_stop','implemented','Stop when a hard resource budget is exhausted.',('stop','budget')),
            ('no_progress_stop','experimental','Stop or switch strategy after sustained zero progress.',('stop','stagnation')),
            ('confidence_stop','experimental','Use calibrated confidence as one input to stopping.',('stop','confidence')),
            ('verification_required','implemented','Block finish when required verifier evidence is missing.',('stop','verification')),
            ('value_of_thought','experimental','Estimate whether another reasoning step has positive value.',('stop','vot')),
            ('abstain','implemented','Return explicit abstention rather than fabricate a result.',('stop','abstain')),
            ('handoff_stop','host_required','Stop local reasoning and hand off to a better solver/operator.',('stop','handoff')),
        )),
        _family('capability_boundary', 'Track where a model/operator is competent and route around known weaknesses.', _rows(
            ('record_success_region','experimental','Record contexts where a solver succeeds.',('capability','success')),
            ('record_failure_region','experimental','Record contexts where a solver fails.',('capability','failure')),
            ('estimate_task_fit','experimental','Estimate fit between current task and solver capabilities.',('capability','fit')),
            ('detect_out_of_distribution','experimental','Detect context far from validated support.',('capability','ood')),
            ('route_to_specialist','host_required','Delegate to a solver with better validated competence.',('capability','route')),
            ('request_new_operator','experimental','Acquire behavioral knowledge for an uncovered capability.',('capability','acquire')),
            ('boundary_probe','experimental','Test near the edge of current competence.',('capability','probe')),
            ('boundary_update','experimental','Update competence estimates from verifier outcomes.',('capability','update')),
        )),
    )
    ids = [row.operator_id for family in families for row in family.suboperators]
    if len(ids) != len(set(ids)):
        raise RuntimeError('default catalog contains duplicate suboperator ids')
    return families
