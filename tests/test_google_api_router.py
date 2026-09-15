import unittest

from runtime.google_api_router import (
    AdapterFailure,
    AdapterResponse,
    ApiRouter,
    CircuitBreaker,
    ConfigValidationError,
    ExecutionBlocked,
    QuotaTracker,
    RequestSpec,
    RouteUnavailable,
    RouterConfigLoader,
)


def table(headers, *rows):
    return [headers, *rows]


def config_tables(
    *,
    route1_project="project-a",
    route1_cred_state="BOUND",
    route1_health="HEALTHY",
    route1_usage=10,
    route2=True,
):
    routes = [
        [
            "route_id", "capability_id", "provider", "service", "api_version",
            "base_endpoint", "method_family", "semantics", "project_ref",
            "credential_ref", "quota_policy_id", "health_id", "priority",
            "weight", "fallback_group", "transformation_required", "enabled",
            "admin_state", "runtime_state", "circuit_state", "config_version",
        ],
        [
            "r1", "file.manage", "google", "drive", "v3",
            "https://www.googleapis.com/drive/v3", "files/*", "collaborative",
            route1_project, "cred1", "q1", "h1", 1, 100, "fg1", False, True,
            "ACTIVE", "READY", "CLOSED", 1,
        ],
    ]
    quota = [
        [
            "quota_policy_id", "route_id", "quota_metric", "hard_limit",
            "soft_limit_pct", "observed_usage", "reserved_capacity",
            "safety_margin", "effective_remaining", "usage_window_sec",
            "quota_state", "critical_limit_pct",
        ],
        ["q1", "r1", "requests_per_minute", 100, .8, route1_usage, 0, 0, 90, 60, "HEALTHY", .9],
    ]
    health = [
        ["health_id", "route_id", "health_state", "consecutive_failures", "circuit_state", "inflight"],
        ["h1", "r1", route1_health, 0, "CLOSED", 0],
    ]
    creds = [
        [
            "credential_ref", "provider", "auth_model", "secret_location",
            "principal_hint", "scopes_class", "project_ref", "state", "enabled",
        ],
        ["cred1", "google", "workload_identity", "/run/keddeh/secrets/ref", "svc-a", "drive", "project-a", route1_cred_state, True],
    ]

    if route2:
        routes.append(
            [
                "r2", "file.manage", "google", "drive", "v3",
                "https://www.googleapis.com/drive/v3", "files/*", "collaborative",
                "project-a", "cred2", "q2", "h2", 1, 50, "fg1", False, True,
                "ACTIVE", "READY", "CLOSED", 1,
            ]
        )
        quota.append(["q2", "r2", "requests_per_minute", 100, .8, 20, 0, 0, 80, 60, "HEALTHY", .9])
        health.append(["h2", "r2", "HEALTHY", 0, "CLOSED", 0])
        creds.append(["cred2", "google", "workload_identity", "/run/keddeh/secrets/ref2", "svc-b", "drive", "project-a", "BOUND", True])

    return {
        "ROUTES": routes,
        "CAPABILITIES": table(
            [
                "capability_id", "target_data_type", "canonical_operation", "semantics",
                "fallback_policy", "enabled",
            ],
            ["file.manage", "File Management", "file.readwrite", "collaborative", "same_semantics_only", True],
        ),
        "QUOTA_POLICY": quota,
        "HEALTH": health,
        "CREDENTIAL_REFS": creds,
        "CONTROL": table(
            ["key", "value"],
            ["config_version", 1],
            ["spreadsheet_role", "POLICY_SOURCE_NOT_REQUEST_PATH"],
            ["fallback_invariant", "SAME_CAPABILITY_SEMANTICS_ONLY"],
            ["credential_invariant", "NO_SECRET_MATERIAL_IN_SHEET"],
            ["execution_gate", "BLOCK_UNBOUND_PROJECT_OR_CREDENTIAL"],
            ["circuit_failure_threshold", 3],
            ["circuit_cooldown_seconds", 60],
        ),
    }


class StaticSource:
    def __init__(self, tables):
        self.tables = tables

    def load_tables(self):
        return self.tables


class FailingSource:
    def load_tables(self):
        raise RuntimeError("control plane temporarily unavailable")


class FakeAdapter:
    service = "drive"

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def execute(self, route, request):
        self.calls.append(route.route_id)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class GoogleApiRouterTests(unittest.TestCase):
    def build_router(self, tables):
        loader = RouterConfigLoader(stale_after_seconds=900)
        loader.refresh(StaticSource(tables), now=1000)
        return loader, ApiRouter(loader, quota_tracker=QuotaTracker())

    def test_unbound_project_is_blocked(self):
        _, router = self.build_router(
            config_tables(route1_project="UNBOUND", route2=False)
        )
        with self.assertRaises(ExecutionBlocked):
            router.select("file.manage")

    def test_last_valid_snapshot_survives_transient_control_plane_failure(self):
        loader = RouterConfigLoader(stale_after_seconds=900)
        first = loader.refresh(StaticSource(config_tables()), now=1000)
        second = loader.refresh(FailingSource(), now=1100)
        self.assertIs(first, second)
        self.assertEqual(second.config_version, 1)

    def test_quota_pressure_prefers_healthier_equivalent_route(self):
        tables = config_tables(route1_usage=95, route2=True)
        _, router = self.build_router(tables)
        decision = router.select("file.manage")
        self.assertEqual(decision.route.route_id, "r2")

    def test_semantic_mismatch_is_not_used_as_fallback(self):
        tables = config_tables(route2=False)
        tables["ROUTES"][1][7] = "collaborative"
        _, router = self.build_router(tables)
        with self.assertRaises(RouteUnavailable):
            router.select("file.manage", semantics="durable_object")

    def test_three_429s_open_circuit(self):
        breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        self.assertEqual(breaker.record_failure("r1", status=429, now=0), "CLOSED")
        self.assertEqual(breaker.record_failure("r1", status=429, now=1), "CLOSED")
        self.assertEqual(breaker.record_failure("r1", status=429, now=2), "OPEN")
        self.assertEqual(breaker.state("r1", now=10), "OPEN")
        self.assertEqual(breaker.state("r1", now=63), "HALF_OPEN")

    def test_401_fails_closed_immediately(self):
        breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        self.assertEqual(breaker.record_failure("r1", status=401, now=0), "OPEN")
        self.assertEqual(breaker.state("r1", now=1), "OPEN")

    def test_secret_bearing_columns_are_rejected(self):
        tables = config_tables()
        tables["CREDENTIAL_REFS"][0].append("client_secret")
        tables["CREDENTIAL_REFS"][1].append("do-not-store-me")
        with self.assertRaises(ConfigValidationError):
            RouterConfigLoader.parse(tables, loaded_at=1000)

    def test_execute_fails_closed_on_authorization_error_without_hopping(self):
        _, router = self.build_router(config_tables())
        adapter = FakeAdapter([AdapterFailure("denied", status=403)])
        request = RequestSpec("GET", "/files")
        with self.assertRaises(ExecutionBlocked):
            router.execute("file.manage", request, {"drive": adapter}, now=lambda: 1200)
        self.assertEqual(adapter.calls, ["r1"])

    def test_execute_can_fail_over_after_retriable_route_failure(self):
        _, router = self.build_router(config_tables())
        adapter = FakeAdapter(
            [
                AdapterFailure("quota", status=429),
                AdapterResponse(status=200, headers={}, body={"ok": True}),
            ]
        )
        request = RequestSpec("GET", "/files")
        response = router.execute("file.manage", request, {"drive": adapter}, now=lambda: 1200)
        self.assertEqual(response.status, 200)
        self.assertEqual(adapter.calls, ["r1", "r2"])


if __name__ == "__main__":
    unittest.main()
