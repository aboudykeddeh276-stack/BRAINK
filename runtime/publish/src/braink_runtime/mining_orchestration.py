from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BladePorts:
    blade_id: str
    role: str
    stratum_port: int
    rpc_port: int
    ipc_port: int
    mux_port: int
    cdp_port: int
    local_nonce_slice: str


@dataclass(frozen=True)
class ProviderEndpoint:
    name: str
    host: str
    port: int
    tls: bool = False


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    algorithm: str
    endpoints: tuple[ProviderEndpoint, ...]
    worker_template: str
    password_env: str
    session_extranonce_owner: str = "PROVIDER_ASSIGNED_AFTER_SUBSCRIBE"


ROLES = (
    "Primary Compute Leader",
    "Execution Blade Tier 1",
    "Execution Blade Tier 1",
    "Execution Blade Tier 1",
    "Execution Blade Tier 1",
    "Execution Blade Tier 1",
    "Execution Blade Tier 1",
    "Dynamic Shard Lane 08",
    "Dynamic Shard Lane 09",
    "Dynamic Shard Lane 10",
    "Dynamic Shard Lane 11",
    "Dynamic Shard Lane 12",
    "Secondary Compute Node",
    "Secondary Compute Node",
    "Hot Standby Failover",
    "Hot Standby Failover",
)

BLADES: tuple[BladePorts, ...] = tuple(
    BladePorts(
        blade_id=f"keddeh.blade{i:02d}",
        role=ROLES[i - 1],
        stratum_port=3332 + i,
        rpc_port=8331 + i,
        ipc_port=9000 + i,
        mux_port=8798 + i,
        cdp_port=9221 + i,
        local_nonce_slice=f"0x{0x4E00 + i:04X} [0x{(i-1)*0x1000:04X}..0x{i*0x1000-1:04X}]",
    )
    for i in range(1, 17)
)

PROVIDERS: dict[str, ProviderProfile] = {
    "VIABTC_BTC": ProviderProfile(
        name="VIABTC_BTC",
        algorithm="SHA-256",
        endpoints=(
            ProviderEndpoint("primary", "btc.viabtc.io", 3333),
            ProviderEndpoint("failover", "btc.viabtc.io", 443),
            ProviderEndpoint("regional", "btc.viabtc.top", 3333),
        ),
        worker_template="{account}.blade{index:02d}",
        password_env="BRAINK_POOL_PASSWORD",
    ),
    "CUSTOM_STRATUM": ProviderProfile(
        name="CUSTOM_STRATUM",
        algorithm="SHA-256",
        endpoints=(),
        worker_template="{account}.blade{index:02d}",
        password_env="BRAINK_POOL_PASSWORD",
    ),
    "BITCOIN_CORE": ProviderProfile(
        name="BITCOIN_CORE",
        algorithm="SHA-256",
        endpoints=(),
        worker_template="{account}.blade{index:02d}",
        password_env="BRAINK_POOL_PASSWORD",
        session_extranonce_owner="LOCAL_SOLO_MINER_RUNTIME",
    ),
}

PROVIDER_ALIASES = {
    "VIABTC": "VIABTC_BTC",
    "BTC_AUTO": "VIABTC_BTC",
}


def normalize_provider(provider_name: str) -> str:
    key = provider_name.strip().upper()
    return PROVIDER_ALIASES.get(key, key)


def validate_port_matrix(blades: Iterable[BladePorts] = BLADES) -> dict:
    blades = tuple(blades)
    categories = {
        "stratum": [b.stratum_port for b in blades],
        "rpc": [b.rpc_port for b in blades],
        "ipc": [b.ipc_port for b in blades],
        "mux": [b.mux_port for b in blades],
        "cdp": [b.cdp_port for b in blades],
    }
    duplicate_within = {
        name: sorted({p for p in ports if ports.count(p) > 1})
        for name, ports in categories.items()
        if len(set(ports)) != len(ports)
    }
    all_ports = [(name, p) for name, ports in categories.items() for p in ports]
    by_port: dict[int, list[str]] = {}
    for name, port in all_ports:
        by_port.setdefault(port, []).append(name)
    cross_collisions = {str(p): names for p, names in by_port.items() if len(names) > 1}
    expected = {
        "stratum": (3333, 3348),
        "rpc": (8332, 8347),
        "ipc": (9001, 9016),
        "mux": (8799, 8814),
        "cdp": (9222, 9237),
    }
    range_errors = {
        name: {"expected": expected[name], "actual": (min(ports), max(ports))}
        for name, ports in categories.items()
        if (min(ports), max(ports)) != expected[name]
    }
    ok = len(blades) == 16 and not duplicate_within and not cross_collisions and not range_errors
    return {
        "status": "PASS" if ok else "FAIL",
        "blade_count": len(blades),
        "port_count": len(all_ports),
        "duplicate_within": duplicate_within,
        "cross_collisions": cross_collisions,
        "range_errors": range_errors,
        "ranges": {k: [min(v), max(v)] for k, v in categories.items()},
    }


def _provider_endpoints(provider: ProviderProfile) -> list[dict]:
    if provider.name != "CUSTOM_STRATUM":
        return [asdict(e) for e in provider.endpoints]
    host = os.getenv("BRAINK_POOL_HOST", "").strip()
    if not host:
        return []
    try:
        port = int(os.getenv("BRAINK_POOL_PORT", "3333"))
    except ValueError:
        port = 3333
    tls = os.getenv("BRAINK_POOL_TLS", "false").strip().lower() in {"1", "true", "yes", "on"}
    return [{"name": "operator", "host": host, "port": port, "tls": tls}]


def render_operator_manifest(provider_name: str, account: str) -> dict:
    key = normalize_provider(provider_name)
    provider = PROVIDERS.get(key)
    if provider is None:
        raise KeyError(f"UNKNOWN_PROVIDER:{key}")
    password_state = "BOUND_FROM_ENV" if (
        os.getenv("BRAINK_STRATUM_PASSWORD", "").strip()
        or os.getenv(provider.password_env, "").strip()
    ) else "UNBOUND_SECRET"
    endpoints = _provider_endpoints(provider)
    workers = []
    for index, blade in enumerate(BLADES, start=1):
        workers.append({
            **asdict(blade),
            "worker": provider.worker_template.format(account=account, index=index),
            "provider": key,
            "provider_endpoints": endpoints,
            "provider_password": password_state,
            "local_nonce_partition": blade.local_nonce_slice,
            "stratum_session_extranonce": provider.session_extranonce_owner,
        })
    return {
        "schema": "braink.kex.mining-orchestration.v2",
        "authority": os.getenv("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR"),
        "provider_role": "EXTERNAL_PROFILE",
        "provider": key,
        "algorithm": provider.algorithm,
        "port_validation": validate_port_matrix(),
        "workers": workers,
        "claim_boundary": {
            "local_port_matrix": "CONFIGURED",
            "local_nonce_partitions": "BRAINK_NAMESPACE_ONLY",
            "provider_extranonce1": provider.session_extranonce_owner,
            "physical_blade_binding": "REQUIRES_OPERATOR_HOST_READBACK",
            "pool_authorization": "REQUIRES_PROVIDER_READBACK",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default=os.getenv("BRAINK_MINING_PROVIDER", "VIABTC_BTC"))
    parser.add_argument("--account", default=os.getenv("BRAINK_MINING_ACCOUNT", "aboudykeddeh276"))
    parser.add_argument("--out", default=os.getenv("BRAINK_MINING_MANIFEST", "./data/mining_orchestration_manifest.json"))
    args = parser.parse_args()
    manifest = render_operator_manifest(args.provider, args.account)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["port_validation"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
