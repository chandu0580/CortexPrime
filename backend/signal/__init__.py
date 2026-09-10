"""The signal fabric — Phase 11.2 (ADR-122).

Where a trusted real signal becomes a canonical, durable, tenant-scoped
CortexPrime event and is handed to detection. Everything here composes what
already exists and verified:

* the **World Plane** (``backend.world``) is the canonical durable event store:
  ``cw_observation`` is append-only, tenant-scoped and identity-deduplicated;
  facts derive from observations; nothing here adds a table;
* the **governed Kubernetes watch** (``backend.api.kubernetes_watch_driver``)
  is the Kubernetes signal source; this package supervises it and enriches
  its events through the existing governed ``pod.get`` read;
* the **Prompt 1 trust boundary** (``backend.safety``) is the only way an
  external signal enters over HTTP; the Alertmanager ingress sits behind it;
* the **SQL leadership store** is the only fencing; the worker holds the
  ``WORLD_WATCH`` role and nothing else.

What this package deliberately is not: an event bus, a queue, a scheduler, a
detector, or a remediation path. It observes, ingests, normalises, persists,
correlates and hands off. It never executes.
"""
