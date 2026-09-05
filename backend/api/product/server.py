"""ASGI entrypoint for the product API.

    uvicorn backend.api.product.server:app --port 8110

Why a separate process
----------------------
The product app is deliberately not mounted into ``backend.main`` (ADR-094): 89
of 96 V1 route modules are tenant-unaware, and a product surface added beside
them inherits their tenant semantics by proximity. Keeping it in its own process
keeps that separation true at runtime rather than only in the import graph.

CORS
----
The browser authenticates with the HttpOnly ``cortex_access`` cookie that the V1
auth service sets, so a cross-origin request must carry credentials -- and a
credentialed request may not use a wildcard origin. Origins are therefore read
from ``CORTEX_PRODUCT_CORS_ORIGINS`` and default to the local dev frontend.
Nothing here is a wildcard, and no header a browser could forge grants anything:
CORS decides which *page* may read a response, never who the caller is. Identity
still comes only from the verified token.
"""

from __future__ import annotations

import os

from fastapi.middleware.cors import CORSMiddleware

from backend.api.product.app import build_product_app

_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _origins() -> list[str]:
    raw = os.getenv("CORTEX_PRODUCT_CORS_ORIGINS", _DEFAULT_ORIGINS)
    # A wildcard is refused rather than silently accepted: with credentialed
    # requests it would let any page read a tenant's investigations.
    return [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]


app = build_product_app()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=True,
    # Read-only by shape: the API registers only GET routes, and the browser is
    # told the same thing rather than being invited to try others.
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
