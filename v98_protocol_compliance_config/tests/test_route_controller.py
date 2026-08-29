from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from keddeh_route_controller import (
    RouteController,
    RouteError,
    RouteLoopDetected,
    RouteNotFound,
    run_route_controller_acceptance,
)


class RouteControllerTests(unittest.TestCase):
    def test_longest_prefix_and_metric_selection(self) -> None:
        controller = RouteController()
        controller.add_route("0.0.0.0/0", "default0", "192.0.2.1", 500)
        controller.add_route("192.0.2.0/24", "default0")
        controller.add_route("10.0.0.0/8", "mesh-slow", None, 200)
        controller.add_route("10.0.0.0/8", "mesh-fast", None, 10)
        controller.add_route("10.20.0.0/16", "mesh-specific", None, 100)
        decision = controller.resolve("10.20.30.40")
        self.assertEqual(decision.matched_prefix, "10.20.0.0/16")
        self.assertEqual(decision.interface, "mesh-specific")
        decision = controller.resolve("10.30.1.1")
        self.assertEqual(decision.interface, "mesh-fast")

    def test_invalid_duplicate_and_unreachable_routes_fail_closed(self) -> None:
        controller = RouteController()
        with self.assertRaises(RouteError):
            controller.add_route("10.0.999.0/24", "bad0")
        route = controller.add_route("10.0.0.0/8", "mesh0")
        with self.assertRaises(RouteError):
            controller.add_route(route.prefix, route.interface, route.next_hop, route.metric)
        with self.assertRaises(RouteNotFound):
            controller.resolve("203.0.113.1")

    def test_next_hop_loop_is_rejected(self) -> None:
        controller = RouteController()
        controller.add_route("10.1.0.0/16", "meshA", "10.2.0.1")
        controller.add_route("10.2.0.0/16", "meshB", "10.1.0.1")
        with self.assertRaises(RouteLoopDetected):
            controller.trace_next_hop("10.1.0.25")
        self.assertFalse(controller.validate()["valid"])

    def test_acceptance_writes_executable_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_route_controller_acceptance(root, emit_receipt=True)
            self.assertTrue(result["positive_test_passed"])
            self.assertTrue(result["negative_test_passed"])
            self.assertFalse(result["kernel_route_table_modified"])
            self.assertFalse(result["packets_transmitted"])
            self.assertTrue(Path(result["receipt_path"]).exists())
            self.assertTrue(Path(result["route_table_path"]).exists())


if __name__ == "__main__":
    unittest.main()
