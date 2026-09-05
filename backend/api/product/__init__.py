"""The governed product API boundary (Phase 10.1, ADR-094).

Read-only, tenant-scoped, and holding no authority. See ``app.py`` for why it is
its own application rather than a router mounted beside the V1 surface.
"""

from backend.api.product.app import ProductEngine, build_product_app

__all__ = ["ProductEngine", "build_product_app"]
