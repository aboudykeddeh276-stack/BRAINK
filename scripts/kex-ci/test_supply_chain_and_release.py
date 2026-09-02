from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.software_supply_chain import SupplyChainLedger, Component, BuildProvenance

ledger = SupplyChainLedger()
ledger.add_component(Component("braink-core", "r11", "KEDDEH_SYSTEMS", "git://BRAINK", "a"*64, "PROPRIETARY"))
ledger.add_component(Component("python", "3.x", "Python Software Foundation", "runtime://python", "b"*64, "PSF-2.0"))
sbom = ledger.sbom("BRAINK", "R11")
assert sbom["sbom_root"]
assert len(sbom["components"]) == 2

ledger.add_build(BuildProvenance(
    "build://r11/1", "c"*64, "agent://builder/a", "workflow://keddeh-enterprise-control",
    ("a"*64, "b"*64), ("d"*64,), 1,
))
prov = ledger.provenance_snapshot()
assert prov["ledger_root"]
assert len(prov["builds"]) == 1

print("SUPPLY_CHAIN_AND_RELEASE_PASS")
