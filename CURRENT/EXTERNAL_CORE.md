# External Core

External Core is the complete non-neural capability substrate. Tools are one subtype inside it, not a peer architecture layer.

`shared/external-core/manifest.json` owns the general capability/tool floor. Each region manifest owns accepted regional External Core bindings. Each AI profile has independent private External Core and private tool-permission slots.

Wave 3 does not fabricate private capabilities. Central's already-accepted Central-only tools and three Central External Core bindings are represented as Central-private source. Chiefs and Specialists begin with empty private External Core/tool lists where accepted evidence contained only regional capabilities; their private slots are explicit and can evolve later.

Effective capabilities are computed by the resolver from shared + regional + private source. Compatibility projections preserve accepted runtime tool permissions and External Core bindings exactly.

Canonical External Core cognitive authorities are independently versioned semantic boundaries rather than one monolithic tool layer. `nolane.external_core.causal` owns bounded causal intervention/program structure, while `nolane.external_core.experimentation` owns finite behavioral version spaces, deterministic informative-probe selection, budgeted pure shadow experiments, independent verification receipts, and evidence-bound experiment ledger state. Experimentation does not own candidate generation or capability acquisition, promotion authority, or cross-domain transfer/meta reuse; those remain separate component boundaries so later extraction cannot silently widen Experimentation's authority.

Experiment receipts persist the canonical version-space hypothesis IDs, selection-probe IDs, verification-probe IDs and selection budget that define their semantic experiment identity. Restore recomputes the content-addressed experiment ID from that envelope before a receipt can be admitted to deterministic ledger state, so changing a serialized experiment ID cannot silently create a new accepted identity.

## Capability acquisition

`external.capability_acquisition` is canonical-native in Wave 5AX. It is a control-plane governor over `external.cognitive_library` and `external.assurance`: candidate generation happens upstream; admitted candidates enter probation against an exact library baseline; independent/challenge/reliability evidence must pass; promotion requires the exact persisted native Assurance receipt bound to the same candidate, evidence set and predecessor baseline. Failed gates quarantine without library mutation. Only promoted records cross the acquisition retrieval firewall, and a post-promotion live failure revokes that visibility even though the Cognitive Library itself remains append-only.
