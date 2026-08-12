"""The Intelligence Plane — governed investigation orchestration.

Intelligence PROPOSES and CONSUMES evidence; it never acts or writes truth. It
queries the World Plane, obtains schema-validated model proposals through the
harness governed model boundary, maintains a durable, crash-safe, replay-safe
investigation state machine, and defers grounding to the World Plane and
verification to the Assurance Plane.

It imports the World read layer, the epistemic/intelligence contracts, and the
durable store (infrastructure only). It imports NO connector, provider SDK,
credential carrier, transport, gateway, scheduler, leadership, harness execution,
shell, browser, or computer-use. Composition supplies the ports. Investigation
never executes.
"""
