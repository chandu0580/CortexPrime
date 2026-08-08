"""Bounded contexts.

Each subpackage owns one context's domain, application, and persistence. The
Constitution's rules for this layer (S2):

* A context never imports another context. They communicate by published
  contract only.
* Nothing reaches into another context's persistence.
* A context may import ``contracts/`` and ``platform/``. It may not import
  ``api/``, ``services/``, or ``legacy/``.

``DEP-LAYERS`` enforces the direction; ``BND-CONTEXT-ISOLATION`` and
``BND-PERSISTENCE`` enforce the boundaries between the contexts the Architecture
Constitution names.
"""
