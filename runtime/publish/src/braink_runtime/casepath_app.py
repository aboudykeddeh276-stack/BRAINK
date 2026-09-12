from __future__ import annotations

from .app import DATA, TOKEN, app, catalog, saas
from .casepath_stripe import build_router
from .telemetry_router import build_telemetry_router

# Additive mounts: the existing BRAINK/KEX runtime remains authoritative.
app.include_router(build_router(saas=saas, catalog=catalog))
app.include_router(build_telemetry_router(data_dir=DATA, auth_token=TOKEN))
