from __future__ import annotations

from .app import app, catalog, saas
from .casepath_stripe import build_router

# Additive mount: the existing BRAINK/KEX runtime remains authoritative.
app.include_router(build_router(saas=saas, catalog=catalog))
