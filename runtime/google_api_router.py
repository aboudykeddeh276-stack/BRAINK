from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Protocol, Sequence


DEFAULT_SPREADSHEET_ID = "1fntX9Rb1Sy6rkxuyVKfBUywkcEHqIjYNIvesIJABOcA"
DEFAULT_REFRESH_SECONDS = 300
DEFAULT_STALE_AFTER_SECONDS = 900

REQUIRED_TABS = (
    "ROUTES",
    "CAPABILITIES",
    "QUOTA_POLICY",
    "HEALTH",
    "CREDENTIAL_REFS",
    "CONTROL",
)

_ALLOWED_HEALTH = {"HEALTHY", "PRESSURED", "RECOVERING", "DEGRADED", "UNKNOWN_UNBOUND"}
_FORBIDDEN_CREDENTIAL_COLUMNS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "password",
    "secret",
    "token",
}


class RouterError(RuntimeError):
    """Base error for the K-SYSTEMS API router."""


class ConfigValidationError(RouterError):
    """The control-plane snapshot is malformed or violates a locked invariant."""


class ConfigUnavailable(RouterError):
    """No valid, non-stale routing snapshot is available."""


class RouteUnavailable(RouterError):
    """No route can safely satisfy the requested capability."""


class ExecutionBlocked(RouterError):
    """A configured route is not yet bound to executable runtime authority."""


class AdapterFailure(RouterError):
    def __init__(self, message: str, *, status: int | None = None, retriable: bool | None = None):
        super().__init__(message)
        self.status = status
        if retriable is None:
            retriable = status in {408, 429} or (status is not None and 500 <= status <= 599)
        self.retriable = bool(retriable)


class TokenProvider(Protocol):
    def __call__(self) -> str:
        """Return a current bearer token. Secret material must not be persisted in the sheet."""


class ConfigSource(Protocol):
    def load_tables(self) -> Mapping[str, Sequence[Sequence[Any]]]:
        """Return spreadsheet tab values, including header rows."""


class ApiAdapter(Protocol):
    service: str

    def execute(self, route: "Route", request: "RequestSpec") -> "AdapterResponse":
        ...


@dataclass(frozen=True)
class Capability:
    capability_id: str
    target_data_type: str
    canonical_operation: str
    semantics: str
    fallback_policy: str
    enabled: bool


@dataclass(frozen=True)
class Route:
    route_id: str
    capability_id: str
    provider: str
    service: str
    api_version: str
    base_endpoint: str
    method_family: str
    semantics: str
    project_ref: str
    credential_ref: str
    quota_policy_id: str
    health_id: str
    priority: int
    weight: int
    fallback_group: str
    transformation_required: bool
    enabled: bool
    admin_state: str
    runtime_state: str
    circuit_state: str
    config_version: int


@dataclass(frozen=True)
class QuotaPolicy:
    quota_policy_id: str
    route_id: str
    quota_metric: str
    hard_limit: float | None
    soft_limit_pct: float
    observed_usage: float
    reserved_capacity: float
    safety_margin: float
    effective_remaining: float | None
    usage_window_sec: int
    quota_state: str
    critical_limit_pct: float

    @property
    def utilization(self) -> float:
        if not self.hard_limit or self.hard_limit <= 0:
            return 0.0
        used = self.observed_usage + self.reserved_capacity + self.safety_margin
        return max(0.0, used / self.hard_limit)


@dataclass(frozen=True)
class Health:
    health_id: str
    route_id: str
    health_state: str
    consecutive_failures: int
    circuit_state: str
    inflight: int


@dataclass(frozen=True)
class CredentialRef:
    credential_ref: str
    provider: str
    auth_model: str
    secret_location: str
    principal_hint: str
    scopes_class: str
    project_ref: str
    state: str
    enabled: bool


@dataclass(frozen=True)
class RouterSnapshot:
    config_version: int
    loaded_at: float
    control: Mapping[str, Any]
    capabilities: Mapping[str, Capability]
    routes: tuple[Route, ...]
    quota_policies: Mapping[str, QuotaPolicy]
    health: Mapping[str, Health]
    credentials: Mapping[str, CredentialRef]


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    capability: Capability
    utilization: float
    health_state: str
    reason: str


@dataclass(frozen=True)
class RequestSpec:
    method: str
    path: str
    query: Mapping[str, str | int | float | bool] = field(default_factory=dict)
    body: Mapping[str, Any] | Sequence[Any] | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    timeout: float = 20.0

    def __post_init__(self) -> None:
        method = self.method.upper()
        object.__setattr__(self, "method", method)
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError(f"unsupported HTTP method: {method}")
        if not self.path.startswith("/"):
            raise ValueError("request path must start with '/'")
        if "authorization" in {k.lower() for k in self.headers}:
            raise ValueError("Authorization must be supplied by the adapter token provider")


@dataclass(frozen=True)
class AdapterResponse:
    status: int
    headers: Mapping[str, str]
    body: Any


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _norm(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n", ""}:
        return False if text != "" else default
    raise ConfigValidationError(f"invalid boolean value: {value!r}")


def _as_int(value: Any, default: int = 0) -> int:
    text = _norm(value)
    if not text:
        return default
    try:
        return int(float(text))
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(f"invalid integer value: {value!r}") from exc


def _as_float(value: Any, default: float = 0.0) -> float:
    text = _norm(value)
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(f"invalid numeric value: {value!r}") from exc


def _as_optional_float(value: Any) -> float | None:
    text = _norm(value)
    if not text:
        return None
    return _as_float(text)


def _rows(values: Sequence[Sequence[Any]], tab: str) -> list[dict[str, Any]]:
    if not values:
        raise ConfigValidationError(f"{tab}: missing header row")
    headers = [_norm(v) for v in values[0]]
    if not all(headers):
        raise ConfigValidationError(f"{tab}: blank header name")
    if len(set(headers)) != len(headers):
        raise ConfigValidationError(f"{tab}: duplicate header")
    out: list[dict[str, Any]] = []
    for raw in values[1:]:
        if not any(_norm(v) for v in raw):
            continue
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        out.append(dict(zip(headers, padded[: len(headers)])))
    return out


class GoogleSheetsValuesSource:
    """Reads a routing snapshot from the Sheets Values API using an injected token provider."""

    def __init__(
        self,
        token_provider: TokenProvider,
        spreadsheet_id: str = DEFAULT_SPREADSHEET_ID,
        *,
        timeout: float = 15.0,
    ) -> None:
        self.token_provider = token_provider
        self.spreadsheet_id = spreadsheet_id
        self.timeout = timeout

    def load_tables(self) -> Mapping[str, Sequence[Sequence[Any]]]:
        query = urllib.parse.urlencode(
            [("ranges", f"{tab}!A:Z") for tab in REQUIRED_TABS],
            doseq=True,
        )
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/"
            f"{urllib.parse.quote(self.spreadsheet_id, safe='')}/values:batchGet?{query}"
        )
        token = self.token_provider().strip()
        if not token:
            raise ConfigUnavailable("token provider returned an empty bearer token")
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ConfigUnavailable(f"Sheets config read failed: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ConfigUnavailable(f"Sheets config read failed: {type(exc).__name__}") from exc

        tables: dict[str, Sequence[Sequence[Any]]] = {}
        ranges = payload.get("valueRanges", [])
        by_prefix = {
            _norm(item.get("range")).split("!", 1)[0].strip("'"): item.get("values", [])
            for item in ranges
        }
        for tab in REQUIRED_TABS:
            if tab not in by_prefix:
                raise ConfigValidationError(f"Sheets response missing required tab: {tab}")
            tables[tab] = by_prefix[tab]
        return tables


class RouterConfigLoader:
    """Validates spreadsheet policy and retains the last valid snapshot across transient failures."""

    def __init__(self, *, stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS) -> None:
        self.stale_after_seconds = stale_after_seconds
        self._snapshot: RouterSnapshot | None = None
        self._lock = threading.RLock()

    @property
    def snapshot(self) -> RouterSnapshot:
        with self._lock:
            if self._snapshot is None:
                raise ConfigUnavailable("no validated routing snapshot is loaded")
            return self._snapshot

    def refresh(self, source: ConfigSource, *, now: float | None = None) -> RouterSnapshot:
        now = time.time() if now is None else now
        try:
            candidate = self.parse(source.load_tables(), loaded_at=now)
        except Exception:
            with self._lock:
                if self._snapshot and now - self._snapshot.loaded_at <= self.stale_after_seconds:
                    return self._snapshot
            raise
        with self._lock:
            if self._snapshot and candidate.config_version < self._snapshot.config_version:
                raise ConfigValidationError(
                    f"config version rollback rejected: {candidate.config_version} < {self._snapshot.config_version}"
                )
            self._snapshot = candidate
            return candidate

    @classmethod
    def parse(
        cls,
        tables: Mapping[str, Sequence[Sequence[Any]]],
        *,
        loaded_at: float | None = None,
    ) -> RouterSnapshot:
        for tab in REQUIRED_TABS:
            if tab not in tables:
                raise ConfigValidationError(f"missing required tab: {tab}")

        credential_values = tables["CREDENTIAL_REFS"]
        if not credential_values:
            raise ConfigValidationError("CREDENTIAL_REFS: missing header row")
        credential_headers = {_norm(v).lower() for v in credential_values[0]}
        forbidden = credential_headers & _FORBIDDEN_CREDENTIAL_COLUMNS
        if forbidden:
            raise ConfigValidationError(
                "CREDENTIAL_REFS contains forbidden secret-bearing columns: " + ",".join(sorted(forbidden))
            )

        control_rows = _rows(tables["CONTROL"], "CONTROL")
        control: dict[str, Any] = {_norm(row.get("key")): row.get("value") for row in control_rows}
        cls._validate_control(control)
        config_version = _as_int(control.get("config_version"))
        if config_version < 1:
            raise ConfigValidationError("CONTROL.config_version must be >= 1")

        capabilities = {}
        for row in _rows(tables["CAPABILITIES"], "CAPABILITIES"):
            obj = Capability(
                capability_id=_norm(row.get("capability_id")),
                target_data_type=_norm(row.get("target_data_type")),
                canonical_operation=_norm(row.get("canonical_operation")),
                semantics=_norm(row.get("semantics")),
                fallback_policy=_norm(row.get("fallback_policy")),
                enabled=_as_bool(row.get("enabled"), True),
            )
            if not obj.capability_id:
                raise ConfigValidationError("CAPABILITIES.capability_id is required")
            capabilities[obj.capability_id] = obj

        routes: list[Route] = []
        route_ids: set[str] = set()
        for row in _rows(tables["ROUTES"], "ROUTES"):
            route = Route(
                route_id=_norm(row.get("route_id")),
                capability_id=_norm(row.get("capability_id")),
                provider=_norm(row.get("provider")),
                service=_norm(row.get("service")),
                api_version=_norm(row.get("api_version")),
                base_endpoint=_norm(row.get("base_endpoint")).rstrip("/"),
                method_family=_norm(row.get("method_family")),
                semantics=_norm(row.get("semantics")),
                project_ref=_norm(row.get("project_ref")),
                credential_ref=_norm(row.get("credential_ref")),
                quota_policy_id=_norm(row.get("quota_policy_id")),
                health_id=_norm(row.get("health_id")),
                priority=max(1, _as_int(row.get("priority"), 1)),
                weight=max(0, _as_int(row.get("weight"), 100)),
                fallback_group=_norm(row.get("fallback_group")),
                transformation_required=_as_bool(row.get("transformation_required")),
                enabled=_as_bool(row.get("enabled"), True),
                admin_state=_norm(row.get("admin_state")).upper(),
                runtime_state=_norm(row.get("runtime_state")).upper(),
                circuit_state=_norm(row.get("circuit_state")).upper(),
                config_version=_as_int(row.get("config_version"), config_version),
            )
            if not route.route_id or not route.capability_id:
                raise ConfigValidationError("ROUTES.route_id and capability_id are required")
            if route.route_id in route_ids:
                raise ConfigValidationError(f"duplicate route_id: {route.route_id}")
            if route.capability_id not in capabilities:
                raise ConfigValidationError(f"{route.route_id}: unknown capability {route.capability_id}")
            if not route.base_endpoint.startswith("https://"):
                raise ConfigValidationError(f"{route.route_id}: base_endpoint must use https")
            if route.config_version > config_version:
                raise ConfigValidationError(
                    f"{route.route_id}: route config_version exceeds CONTROL.config_version"
                )
            route_ids.add(route.route_id)
            routes.append(route)

        quota_policies = {}
        for row in _rows(tables["QUOTA_POLICY"], "QUOTA_POLICY"):
            obj = QuotaPolicy(
                quota_policy_id=_norm(row.get("quota_policy_id")),
                route_id=_norm(row.get("route_id")),
                quota_metric=_norm(row.get("quota_metric")),
                hard_limit=_as_optional_float(row.get("hard_limit")),
                soft_limit_pct=_as_float(row.get("soft_limit_pct"), 0.8),
                observed_usage=_as_float(row.get("observed_usage"), 0.0),
                reserved_capacity=_as_float(row.get("reserved_capacity"), 0.0),
                safety_margin=_as_float(row.get("safety_margin"), 0.0),
                effective_remaining=_as_optional_float(row.get("effective_remaining")),
                usage_window_sec=max(1, _as_int(row.get("usage_window_sec"), 60)),
                quota_state=_norm(row.get("quota_state")).upper(),
                critical_limit_pct=_as_float(row.get("critical_limit_pct"), 0.9),
            )
            if obj.route_id not in route_ids:
                raise ConfigValidationError(f"{obj.quota_policy_id}: unknown route {obj.route_id}")
            if not (0 < obj.soft_limit_pct <= obj.critical_limit_pct <= 1.0):
                raise ConfigValidationError(
                    f"{obj.quota_policy_id}: require 0 < soft <= critical <= 1"
                )
            quota_policies[obj.quota_policy_id] = obj

        health = {}
        for row in _rows(tables["HEALTH"], "HEALTH"):
            obj = Health(
                health_id=_norm(row.get("health_id")),
                route_id=_norm(row.get("route_id")),
                health_state=_norm(row.get("health_state")).upper(),
                consecutive_failures=max(0, _as_int(row.get("consecutive_failures"), 0)),
                circuit_state=_norm(row.get("circuit_state")).upper() or "CLOSED",
                inflight=max(0, _as_int(row.get("inflight"), 0)),
            )
            if obj.route_id not in route_ids:
                raise ConfigValidationError(f"{obj.health_id}: unknown route {obj.route_id}")
            if obj.health_state not in _ALLOWED_HEALTH:
                raise ConfigValidationError(f"{obj.health_id}: unsupported health state {obj.health_state}")
            health[obj.health_id] = obj

        credentials = {}
        for row in _rows(credential_values, "CREDENTIAL_REFS"):
            obj = CredentialRef(
                credential_ref=_norm(row.get("credential_ref")),
                provider=_norm(row.get("provider")),
                auth_model=_norm(row.get("auth_model")),
                secret_location=_norm(row.get("secret_location")),
                principal_hint=_norm(row.get("principal_hint")),
                scopes_class=_norm(row.get("scopes_class")),
                project_ref=_norm(row.get("project_ref")),
                state=_norm(row.get("state")).upper(),
                enabled=_as_bool(row.get("enabled")),
            )
            if not obj.credential_ref:
                raise ConfigValidationError("CREDENTIAL_REFS.credential_ref is required")
            credentials[obj.credential_ref] = obj

        for route in routes:
            if route.quota_policy_id not in quota_policies:
                raise ConfigValidationError(f"{route.route_id}: missing quota policy {route.quota_policy_id}")
            if route.health_id not in health:
                raise ConfigValidationError(f"{route.route_id}: missing health record {route.health_id}")
            if route.credential_ref not in credentials:
                raise ConfigValidationError(f"{route.route_id}: missing credential ref {route.credential_ref}")

        return RouterSnapshot(
            config_version=config_version,
            loaded_at=time.time() if loaded_at is None else loaded_at,
            control=control,
            capabilities=capabilities,
            routes=tuple(routes),
            quota_policies=quota_policies,
            health=health,
            credentials=credentials,
        )

    @staticmethod
    def _validate_control(control: Mapping[str, Any]) -> None:
        required = {
            "spreadsheet_role": "POLICY_SOURCE_NOT_REQUEST_PATH",
            "fallback_invariant": "SAME_CAPABILITY_SEMANTICS_ONLY",
            "credential_invariant": "NO_SECRET_MATERIAL_IN_SHEET",
            "execution_gate": "BLOCK_UNBOUND_PROJECT_OR_CREDENTIAL",
        }
        for key, expected in required.items():
            actual = _norm(control.get(key)).upper()
            if actual != expected:
                raise ConfigValidationError(f"locked invariant {key} must equal {expected}")


class QuotaTracker:
    """Local request accounting, kept off the spreadsheet hot path."""

    def __init__(self) -> None:
        self._events: MutableMapping[str, deque[float]] = defaultdict(deque)
        self._reserved: MutableMapping[str, int] = defaultdict(int)
        self._lock = threading.RLock()

    def _trim(self, route_id: str, window_seconds: int, now: float) -> None:
        q = self._events[route_id]
        cutoff = now - window_seconds
        while q and q[0] <= cutoff:
            q.popleft()

    def observe(self, route_id: str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._events[route_id].append(now)

    def reserve(self, route_id: str, amount: int = 1) -> None:
        if amount < 1:
            raise ValueError("reservation amount must be >= 1")
        with self._lock:
            self._reserved[route_id] += amount

    def release(self, route_id: str, amount: int = 1) -> None:
        with self._lock:
            self._reserved[route_id] = max(0, self._reserved[route_id] - max(1, amount))

    def local_usage(self, route_id: str, window_seconds: int, *, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self._lock:
            self._trim(route_id, window_seconds, now)
            return len(self._events[route_id]) + self._reserved[route_id]

    def utilization(
        self,
        route_id: str,
        policy: QuotaPolicy,
        *,
        now: float | None = None,
    ) -> float:
        if not policy.hard_limit or policy.hard_limit <= 0:
            return policy.utilization
        local = self.local_usage(route_id, policy.usage_window_sec, now=now)
        observed = max(policy.observed_usage, float(local))
        return max(
            0.0,
            (observed + policy.reserved_capacity + policy.safety_margin) / policy.hard_limit,
        )


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 3, cooldown_seconds: int = 60) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1, cooldown_seconds)
        self._failures: MutableMapping[str, int] = defaultdict(int)
        self._opened_at: dict[str, float] = {}
        self._lock = threading.RLock()

    def state(self, route_id: str, *, now: float | None = None) -> str:
        now = time.time() if now is None else now
        with self._lock:
            opened = self._opened_at.get(route_id)
            if opened is None:
                return "CLOSED"
            if now - opened >= self.cooldown_seconds:
                return "HALF_OPEN"
            return "OPEN"

    def record_success(self, route_id: str) -> None:
        with self._lock:
            self._failures.pop(route_id, None)
            self._opened_at.pop(route_id, None)

    def record_failure(
        self,
        route_id: str,
        *,
        status: int | None = None,
        now: float | None = None,
    ) -> str:
        now = time.time() if now is None else now
        with self._lock:
            if status in {401, 403}:
                self._failures[route_id] = self.failure_threshold
                self._opened_at[route_id] = now
                return "OPEN"
            self._failures[route_id] += 1
            if self._failures[route_id] >= self.failure_threshold:
                self._opened_at[route_id] = now
                return "OPEN"
            return "CLOSED"


class ApiRouter:
    def __init__(
        self,
        loader: RouterConfigLoader,
        *,
        quota_tracker: QuotaTracker | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.loader = loader
        self.quota_tracker = quota_tracker or QuotaTracker()
        snapshot = loader.snapshot
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=_as_int(snapshot.control.get("circuit_failure_threshold"), 3),
            cooldown_seconds=_as_int(snapshot.control.get("circuit_cooldown_seconds"), 60),
        )

    def _route_bound(self, route: Route, snapshot: RouterSnapshot) -> tuple[bool, str]:
        credential = snapshot.credentials[route.credential_ref]
        if route.project_ref.upper() in {"", "UNBOUND", "DISCOVERY_REQUIRED"}:
            return False, "project_ref is unbound"
        if not credential.enabled or credential.state in {"", "UNBOUND", "DISABLED"}:
            return False, "credential_ref is unbound or disabled"
        if credential.project_ref.upper() not in {"", "UNBOUND"} and credential.project_ref != route.project_ref:
            return False, "credential project_ref does not match route project_ref"
        return True, "bound"

    def select(
        self,
        capability_id: str,
        *,
        semantics: str | None = None,
        require_bound: bool = True,
        exclude_route_ids: Iterable[str] = (),
        now: float | None = None,
    ) -> RouteDecision:
        snapshot = self.loader.snapshot
        now = time.time() if now is None else now
        capability = snapshot.capabilities.get(capability_id)
        if not capability or not capability.enabled:
            raise RouteUnavailable(f"capability unavailable: {capability_id}")

        excluded = set(exclude_route_ids)
        candidates: list[tuple[tuple[Any, ...], RouteDecision]] = []
        blocked: list[str] = []

        for route in snapshot.routes:
            if route.route_id in excluded or route.capability_id != capability_id:
                continue
            if not route.enabled or route.admin_state != "ACTIVE":
                continue

            requested_semantics = semantics or route.semantics
            if requested_semantics != route.semantics and not route.transformation_required:
                continue
            if semantics is not None and requested_semantics != route.semantics:
                continue

            sheet_health = snapshot.health[route.health_id]
            if route.circuit_state == "OPEN" or sheet_health.circuit_state == "OPEN":
                continue
            live_circuit = self.circuit_breaker.state(route.route_id, now=now)
            if live_circuit == "OPEN":
                continue

            if sheet_health.health_state == "UNKNOWN_UNBOUND" and require_bound:
                blocked.append(f"{route.route_id}: health unbound")
                continue

            bound, reason = self._route_bound(route, snapshot)
            if require_bound and not bound:
                blocked.append(f"{route.route_id}: {reason}")
                continue

            policy = snapshot.quota_policies[route.quota_policy_id]
            utilization = self.quota_tracker.utilization(route.route_id, policy, now=now)
            if policy.hard_limit is not None and utilization >= 1.0:
                continue

            health_rank = {
                "HEALTHY": 0,
                "RECOVERING": 1,
                "PRESSURED": 2,
                "DEGRADED": 3,
                "UNKNOWN_UNBOUND": 4,
            }.get(sheet_health.health_state, 5)
            pressure_rank = 2 if utilization >= policy.critical_limit_pct else 1 if utilization >= policy.soft_limit_pct else 0
            decision = RouteDecision(
                route=route,
                capability=capability,
                utilization=utilization,
                health_state=sheet_health.health_state,
                reason=f"priority={route.priority};health={sheet_health.health_state};utilization={utilization:.6f}",
            )
            score = (route.priority, pressure_rank, health_rank, utilization, -route.weight, route.route_id)
            candidates.append((score, decision))

        if not candidates:
            if blocked:
                raise ExecutionBlocked("; ".join(blocked))
            raise RouteUnavailable(f"no safe route for capability {capability_id}")

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def execute(
        self,
        capability_id: str,
        request: RequestSpec,
        adapters: Mapping[str, ApiAdapter],
        *,
        semantics: str | None = None,
        max_attempts: int = 3,
        now: Callable[[], float] = time.time,
    ) -> AdapterResponse:
        attempted: set[str] = set()
        last_error: Exception | None = None

        for _ in range(max(1, max_attempts)):
            decision = self.select(
                capability_id,
                semantics=semantics,
                require_bound=True,
                exclude_route_ids=attempted,
                now=now(),
            )
            route = decision.route
            attempted.add(route.route_id)
            adapter = adapters.get(route.service)
            if adapter is None:
                raise ExecutionBlocked(f"{route.route_id}: no adapter registered for service {route.service}")
            if adapter.service != route.service:
                raise ExecutionBlocked(
                    f"{route.route_id}: adapter service mismatch {adapter.service!r} != {route.service!r}"
                )

            self.quota_tracker.reserve(route.route_id)
            try:
                response = adapter.execute(route, request)
                self.quota_tracker.observe(route.route_id, now=now())
                self.circuit_breaker.record_success(route.route_id)
                return response
            except AdapterFailure as exc:
                last_error = exc
                state = self.circuit_breaker.record_failure(
                    route.route_id, status=exc.status, now=now()
                )
                if exc.status in {401, 403}:
                    raise ExecutionBlocked(
                        f"{route.route_id}: authorization failed closed with HTTP {exc.status}"
                    ) from exc
                if not exc.retriable:
                    raise
                if state != "OPEN" and len(attempted) >= max_attempts:
                    raise
            finally:
                self.quota_tracker.release(route.route_id)

        if last_error:
            raise RouteUnavailable(f"all eligible routes failed: {last_error}") from last_error
        raise RouteUnavailable(f"no executable route for capability {capability_id}")


class GoogleRestAdapter:
    """Minimal Google REST execution adapter with bearer-token injection and bounded JSON handling."""

    service = ""

    def __init__(self, token_provider: TokenProvider) -> None:
        if not self.service:
            raise TypeError("GoogleRestAdapter subclass must declare service")
        self.token_provider = token_provider

    def execute(self, route: Route, request: RequestSpec) -> AdapterResponse:
        if route.service != self.service:
            raise ExecutionBlocked(f"adapter {self.service} cannot execute route service {route.service}")
        token = self.token_provider().strip()
        if not token:
            raise ExecutionBlocked(f"{route.route_id}: token provider returned no token")

        query = urllib.parse.urlencode(request.query)
        url = route.base_endpoint + request.path + (("?" + query) if query else "")
        body_bytes = None
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        headers.update(dict(request.headers))
        if request.body is not None:
            body_bytes = json.dumps(request.body, separators=(",", ":")).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=request.method)
        try:
            with urllib.request.urlopen(req, timeout=request.timeout) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
                if raw and "json" in content_type.lower():
                    parsed: Any = json.loads(raw.decode("utf-8"))
                elif raw:
                    parsed = raw.decode("utf-8", errors="replace")
                else:
                    parsed = None
                return AdapterResponse(
                    status=int(response.status),
                    headers=dict(response.headers.items()),
                    body=parsed,
                )
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            raise AdapterFailure(
                f"{route.route_id}: HTTP {exc.code}: {detail[:500]}",
                status=int(exc.code),
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AdapterFailure(
                f"{route.route_id}: transport failure {type(exc).__name__}",
                status=None,
                retriable=True,
            ) from exc


class DriveAdapter(GoogleRestAdapter):
    service = "drive"


class CloudStorageAdapter(GoogleRestAdapter):
    service = "cloud_storage"


class SheetsAdapter(GoogleRestAdapter):
    service = "sheets"


class MonitoringAdapter(GoogleRestAdapter):
    service = "cloud_monitoring"


class BigQueryAdapter(GoogleRestAdapter):
    service = "bigquery"


class PubSubAdapter(GoogleRestAdapter):
    service = "pubsub"


def build_google_adapters(token_provider: TokenProvider) -> dict[str, ApiAdapter]:
    adapters: list[ApiAdapter] = [
        DriveAdapter(token_provider),
        CloudStorageAdapter(token_provider),
        SheetsAdapter(token_provider),
        MonitoringAdapter(token_provider),
        BigQueryAdapter(token_provider),
        PubSubAdapter(token_provider),
    ]
    return {adapter.service: adapter for adapter in adapters}
