#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class RouteError(ValueError):
    pass


class RouteNotFound(RouteError):
    pass


class RouteLoopDetected(RouteError):
    pass


@dataclass(frozen=True)
class Route:
    prefix: str
    interface: str
    next_hop: Optional[str] = None
    metric: int = 100

    def network(self) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
        return ipaddress.ip_network(self.prefix, strict=False)


@dataclass(frozen=True)
class RouteDecision:
    destination: str
    matched_prefix: str
    interface: str
    next_hop: Optional[str]
    metric: int


class RouteController:
    """Deterministic in-process routing control plane.

    It models route registration, validation, longest-prefix selection, metric
    ordering and next-hop loop detection. It does not alter the host kernel route
    table or transmit packets; those remain target-host/network-adapter concerns.
    """

    def __init__(self) -> None:
        self._routes: List[Route] = []

    @property
    def routes(self) -> Tuple[Route, ...]:
        return tuple(self._routes)

    def add_route(
        self,
        prefix: str,
        interface: str,
        next_hop: Optional[str] = None,
        metric: int = 100,
    ) -> Route:
        try:
            network = ipaddress.ip_network(prefix, strict=False)
        except ValueError as exc:
            raise RouteError(f"invalid_prefix:{prefix}") from exc
        if not interface or not interface.strip():
            raise RouteError("interface_required")
        if not isinstance(metric, int) or metric < 0:
            raise RouteError("metric_must_be_non_negative_integer")
        normalized_next_hop: Optional[str] = None
        if next_hop is not None:
            try:
                address = ipaddress.ip_address(next_hop)
            except ValueError as exc:
                raise RouteError(f"invalid_next_hop:{next_hop}") from exc
            if address.version != network.version:
                raise RouteError("address_family_mismatch")
            normalized_next_hop = str(address)
        route = Route(str(network), interface.strip(), normalized_next_hop, metric)
        if route in self._routes:
            raise RouteError("duplicate_route")
        self._routes.append(route)
        return route

    def remove_route(self, route: Route) -> None:
        try:
            self._routes.remove(route)
        except ValueError as exc:
            raise RouteError("route_not_registered") from exc

    def _select_route(self, destination: str, excluded: Set[Route] | None = None) -> Route:
        try:
            address = ipaddress.ip_address(destination)
        except ValueError as exc:
            raise RouteError(f"invalid_destination:{destination}") from exc
        excluded = excluded or set()
        candidates = [
            route
            for route in self._routes
            if route not in excluded
            and route.network().version == address.version
            and address in route.network()
        ]
        if not candidates:
            raise RouteNotFound(f"no_route:{address}")
        candidates.sort(
            key=lambda route: (
                -route.network().prefixlen,
                route.metric,
                route.interface,
                route.next_hop or "",
            )
        )
        return candidates[0]

    def resolve(self, destination: str) -> RouteDecision:
        route = self._select_route(destination)
        return RouteDecision(
            destination=str(ipaddress.ip_address(destination)),
            matched_prefix=route.prefix,
            interface=route.interface,
            next_hop=route.next_hop,
            metric=route.metric,
        )

    def trace_next_hop(self, destination: str, max_hops: int = 32) -> List[RouteDecision]:
        if max_hops < 1:
            raise RouteError("max_hops_must_be_positive")
        current = str(ipaddress.ip_address(destination))
        path: List[RouteDecision] = []
        visited: Set[Tuple[str, str, Optional[str], int]] = set()
        for _ in range(max_hops):
            route = self._select_route(current)
            identity = (route.prefix, route.interface, route.next_hop, route.metric)
            if identity in visited:
                raise RouteLoopDetected(f"route_loop:{route.prefix}")
            visited.add(identity)
            decision = RouteDecision(
                destination=current,
                matched_prefix=route.prefix,
                interface=route.interface,
                next_hop=route.next_hop,
                metric=route.metric,
            )
            path.append(decision)
            if route.next_hop is None:
                return path
            current = route.next_hop
        raise RouteLoopDetected("max_hops_exceeded")

    def validate(self) -> Dict[str, Any]:
        duplicate_count = len(self._routes) - len(set(self._routes))
        loop_errors: List[str] = []
        for route in self._routes:
            sample = route.next_hop or str(next(route.network().hosts(), route.network().network_address))
            try:
                self.trace_next_hop(sample)
            except RouteNotFound:
                if route.next_hop is not None:
                    loop_errors.append(f"unreachable_next_hop:{route.next_hop}")
            except RouteLoopDetected as exc:
                loop_errors.append(str(exc))
        return {
            "route_count": len(self._routes),
            "duplicates": duplicate_count,
            "loop_errors": sorted(set(loop_errors)),
            "valid": duplicate_count == 0 and not loop_errors,
        }

    def export(self) -> List[Dict[str, Any]]:
        return [
            asdict(route)
            for route in sorted(
                self._routes,
                key=lambda route: (
                    route.network().version,
                    int(route.network().network_address),
                    -route.network().prefixlen,
                    route.metric,
                    route.interface,
                ),
            )
        ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_route_controller_acceptance(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    controller = RouteController()
    controller.add_route("0.0.0.0/0", "uplink0", "192.0.2.1", 500)
    controller.add_route("192.0.2.0/24", "uplink0", None, 10)
    controller.add_route("10.10.0.0/16", "mesh0", None, 100)
    controller.add_route("10.10.20.0/24", "mesh1", "10.10.0.1", 20)

    decision = controller.resolve("10.10.20.55")
    path = controller.trace_next_hop("10.10.20.55")
    validation = controller.validate()
    positive_test_passed = (
        decision.matched_prefix == "10.10.20.0/24"
        and decision.interface == "mesh1"
        and decision.next_hop == "10.10.0.1"
        and len(path) == 2
        and path[-1].interface == "mesh0"
        and validation["valid"] is True
    )

    malformed_rejected = False
    unreachable_rejected = False
    loop_rejected = False
    try:
        controller.add_route("10.10.999.0/24", "bad0")
    except RouteError:
        malformed_rejected = True
    isolated = RouteController()
    isolated.add_route("10.0.0.0/8", "local0")
    try:
        isolated.resolve("203.0.113.9")
    except RouteNotFound:
        unreachable_rejected = True
    looped = RouteController()
    looped.add_route("10.1.0.0/16", "meshA", "10.2.0.1")
    looped.add_route("10.2.0.0/16", "meshB", "10.1.0.1")
    try:
        looped.trace_next_hop("10.1.0.25")
    except RouteLoopDetected:
        loop_rejected = True
    negative_test_passed = malformed_rejected and unreachable_rejected and loop_rejected

    route_table_path = root / "runtime_volume" / "network" / "route_table.json"
    receipt_path = root / "evidence" / "route_controller_receipt.json"
    write_json(route_table_path, {"routes": controller.export()})
    payload = {
        "service_id": "indefinite_network_runtime",
        "abstraction": "deterministic_in_process_route_control_plane",
        "kernel_route_table_modified": False,
        "packets_transmitted": False,
        "positive_test_passed": positive_test_passed,
        "negative_test_passed": negative_test_passed,
        "decision": asdict(decision),
        "next_hop_path": [asdict(item) for item in path],
        "validation": validation,
        "negative_vectors": {
            "malformed_prefix_rejected": malformed_rejected,
            "unreachable_destination_rejected": unreachable_rejected,
            "routing_loop_rejected": loop_rejected,
        },
        "route_table_path": str(route_table_path),
        "timestamp": time.time(),
    }
    if emit_receipt:
        write_json(receipt_path, payload)
    payload["receipt_path"] = str(receipt_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args()
    result = run_route_controller_acceptance(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["positive_test_passed"] and result["negative_test_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
