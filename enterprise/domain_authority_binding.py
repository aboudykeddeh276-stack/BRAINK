from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib.util
import sys


class DomainAuthorityBinding:
    """Bind BRAINK domain intent to the resident SERVERS-KEDDEHSYSTEMS registrar/DNS implementation.

    This class deliberately does not reimplement registrar or DNS behavior. It loads the owning
    repository's real module, redirects only its SQLite backing for the current runtime, invokes
    its exported mutation/readback functions, and can load the resident DNS server against the
    same registrar module for wire-protocol qualification.
    """

    def __init__(self, registrar_path: str | Path, state_root: str | Path):
        self.registrar_path = Path(registrar_path).resolve()
        self.state_root = Path(state_root).resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        if not self.registrar_path.is_file():
            raise FileNotFoundError(self.registrar_path)
        self.registrar = self._load_module("kex_registrar_service", self.registrar_path)
        self.registrar.LEDGER_PATH = self.state_root / "keddeh_registrar.sqlite"
        self.registrar.init_registrar_db()

    @staticmethod
    def _load_module(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"MODULE_LOAD_FAILED:{path}")
        mod = importlib.util.module_from_spec(spec)
        prior = sys.modules.get(name)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior
            raise
        return mod

    def register_domain_authority(
        self,
        *,
        domain: str,
        ip: str,
        port: int,
        owner: str,
        primary_ns: str,
        admin_rname: str,
        serial: int,
        records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        zone = domain.rstrip(".")
        self.registrar.register_domain(zone, ip, int(port), owner)
        self.registrar.register_zone(zone, primary_ns, admin_rname, int(serial), owner)
        for record in records or []:
            self.registrar.upsert_record(
                zone,
                record["name"],
                record["type"],
                record["value"],
                record.get("ttl", 300),
                record.get("priority"),
            )
        return self.readback(zone)

    def readback(self, domain: str) -> dict[str, Any]:
        zone = domain.rstrip(".")
        z = self.registrar.get_zone(zone)
        return {
            "status": "READ_BACK" if z else "NOT_FOUND",
            "domain": zone,
            "resolved_ip": self.registrar.resolve_domain(zone),
            "zone": z,
            "records": {
                rrtype: self.registrar.get_records(zone, rrtype)
                for rrtype in ("A", "AAAA", "NS", "CNAME", "MX", "TXT", "CAA")
            },
            "ledger_path": str(self.registrar.LEDGER_PATH),
            "authority_owner": "SERVERS-KEDDEHSYSTEMS/runtime/domain_authority",
        }

    def load_dns_runtime(self, dns_path: str | Path):
        dns_path = Path(dns_path).resolve()
        if not dns_path.is_file():
            raise FileNotFoundError(dns_path)
        # kex_dns imports registrar functions by module name. The exact resident registrar loaded
        # above remains the module bound to that name, so DNS consumes the same authority state.
        sys.modules["kex_registrar_service"] = self.registrar
        return self._load_module("kex_dns_bound_runtime", dns_path)
