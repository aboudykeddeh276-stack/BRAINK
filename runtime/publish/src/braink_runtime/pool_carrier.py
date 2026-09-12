from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from .stratum_carrier import (
    StratumEndpoint,
    VIABTC_ENDPOINTS,
    probe_btc_with_failover,
    probe_stratum,
)


class PoolProfileError(ValueError):
    pass


def available_pool_profiles() -> list[str]:
    return ["VIABTC_BTC", "CUSTOM_STRATUM", *sorted(VIABTC_ENDPOINTS)]


def custom_endpoint_from_env() -> StratumEndpoint:
    host = os.getenv("BRAINK_POOL_HOST", "").strip()
    if not host:
        raise PoolProfileError("BRAINK_POOL_HOST_REQUIRED")
    try:
        port = int(os.getenv("BRAINK_POOL_PORT", "3333"))
    except ValueError as exc:
        raise PoolProfileError("BRAINK_POOL_PORT_INVALID") from exc
    if not (1 <= port <= 65535):
        raise PoolProfileError("BRAINK_POOL_PORT_OUT_OF_RANGE")
    tls = os.getenv("BRAINK_POOL_TLS", "false").strip().lower() in {"1", "true", "yes", "on"}
    return StratumEndpoint(
        name="CUSTOM_STRATUM",
        host=host,
        port=port,
        tls=tls,
        purpose=os.getenv("BRAINK_POOL_PURPOSE", "BTC").strip() or "BTC",
        authority=os.getenv("BRAINK_POOL_AUTHORITY", "USER_OPERATOR_PROFILE").strip() or "USER_OPERATOR_PROFILE",
    )


async def probe_provider(
    profile: str,
    *,
    worker_name: str | None,
    password: str,
    timeout_s: float,
    observe_s: float,
) -> dict[str, Any]:
    key = profile.strip().upper()
    if key in {"VIABTC", "VIABTC_BTC", "BTC_AUTO"}:
        receipt = await probe_btc_with_failover(
            worker_name=worker_name,
            password=password,
            timeout_s=timeout_s,
            observe_s=observe_s,
        )
        receipt["provider_profile"] = "VIABTC_BTC"
        receipt["provider_role"] = "EXTERNAL_PROFILE"
        return receipt
    if key == "CUSTOM_STRATUM":
        endpoint = custom_endpoint_from_env()
        receipt = await probe_stratum(
            endpoint,
            worker_name=worker_name,
            password=password,
            timeout_s=timeout_s,
            observe_s=observe_s,
        )
        receipt["provider_profile"] = "CUSTOM_STRATUM"
        receipt["provider_role"] = "EXTERNAL_PROFILE"
        return receipt
    endpoint = VIABTC_ENDPOINTS.get(key)
    if endpoint is not None:
        receipt = await probe_stratum(
            endpoint,
            worker_name=worker_name,
            password=password,
            timeout_s=timeout_s,
            observe_s=observe_s,
        )
        receipt["provider_profile"] = key
        receipt["provider_role"] = "EXTERNAL_PROFILE"
        return receipt
    raise PoolProfileError(f"UNKNOWN_POOL_PROFILE:{key}")
