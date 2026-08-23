# External Core

External Core is the complete non-neural capability substrate. Tools are one subtype inside it, not a peer architecture layer.

`shared/external-core/manifest.json` owns the general capability/tool floor. Each region manifest owns accepted regional External Core bindings. Each AI profile has independent private External Core and private tool-permission slots.

Wave 3 does not fabricate private capabilities. Central's already-accepted Central-only tools and three Central External Core bindings are represented as Central-private source. Chiefs and Specialists begin with empty private External Core/tool lists where accepted evidence contained only regional capabilities; their private slots are explicit and can evolve later.

Effective capabilities are computed by the resolver from shared + regional + private source. Compatibility projections preserve accepted runtime tool permissions and External Core bindings exactly.
