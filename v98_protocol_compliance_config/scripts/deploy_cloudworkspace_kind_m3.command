#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-keddeh-m3}"
IMAGE="${IMAGE:-cloudworkspace-engine:local}"
NAMESPACE="keddeh-sovereign-mesh"
MANIFEST="$ROOT/deploy/cloudworkspace-engine/cloudworkspace-engine.yaml"
SERVICE_DIR="$ROOT/services/cloudworkspace_engine"
EVIDENCE_DIR="$ROOT/evidence"
PORT_FORWARD_LOG="$EVIDENCE_DIR/cloudworkspace_port_forward.log"

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
info() { printf '[INFO] %s\n' "$*"; }

[[ "$(uname -s)" == "Darwin" ]] || fail "macOS is required"
[[ "$(uname -m)" == "arm64" ]] || fail "Apple-silicon ARM64 is required"
for cmd in docker kind kubectl curl python3; do
  command -v "$cmd" >/dev/null || fail "$cmd is required"
done
docker info >/dev/null 2>&1 || fail "Docker daemon is not running"
mkdir -p "$EVIDENCE_DIR"

if ! kind get clusters | grep -qx "$CLUSTER_NAME"; then
  info "Creating ARM64 kind cluster $CLUSTER_NAME"
  kind create cluster --name "$CLUSTER_NAME" --wait 120s
fi
kubectl config use-context "kind-$CLUSTER_NAME" >/dev/null

info "Building runnable CloudWorkspaceEngine image"
docker build --platform linux/arm64 -t "$IMAGE" "$SERVICE_DIR"
kind load docker-image "$IMAGE" --name "$CLUSTER_NAME"

info "Applying sovereign mesh manifests"
kubectl apply -f "$MANIFEST"
kubectl -n "$NAMESPACE" set image deployment/cloudworkspace-engine cloudworkspace-engine="$IMAGE"
kubectl -n "$NAMESPACE" patch deployment cloudworkspace-engine --type merge -p '{"spec":{"template":{"spec":{"containers":[{"name":"cloudworkspace-engine","imagePullPolicy":"IfNotPresent"}]}}}}'

info "Waiting for rollout"
kubectl -n "$NAMESPACE" rollout status deployment/cloudworkspace-engine --timeout=180s
kubectl -n "$NAMESPACE" get pods -o wide
kubectl -n "$NAMESPACE" get service cloudworkspace-engine

info "Testing live startup, liveness and readiness endpoints"
rm -f "$PORT_FORWARD_LOG"
kubectl -n "$NAMESPACE" port-forward service/cloudworkspace-engine 18080:8080 >"$PORT_FORWARD_LOG" 2>&1 &
PF_PID=$!
trap 'kill "$PF_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/healthz >/dev/null 2>&1; then break; fi
  sleep 1
done

STARTUP="$(curl -fsS http://127.0.0.1:18080/startupz)"
HEALTH="$(curl -fsS http://127.0.0.1:18080/healthz)"
READY="$(curl -fsS http://127.0.0.1:18080/readyz)"
METRICS="$(curl -fsS http://127.0.0.1:18080/metrics)"

python3 - "$STARTUP" "$HEALTH" "$READY" "$METRICS" "$IMAGE" "$CLUSTER_NAME" > "$EVIDENCE_DIR/cloudworkspace_kind_m3_receipt.json" <<'PY'
import hashlib, json, platform, sys, time
startup, health, ready, metrics = [json.loads(x) for x in sys.argv[1:5]]
image, cluster = sys.argv[5:7]
receipt = {
    "version": "V106-CLOUDWORKSPACE-KIND-M3-1",
    "cluster": cluster,
    "image": image,
    "host": {"system": platform.system(), "machine": platform.machine()},
    "startup": startup,
    "health": health,
    "readiness": ready,
    "metrics": metrics,
    "checks": {
        "startup": startup.get("state") == "STARTED",
        "health": health.get("state") == "HEALTHY",
        "readiness": ready.get("state") == "READY",
        "bounded_failure": ready.get("globalStop") is False,
    },
    "timestamp": time.time(),
}
receipt["promotion_state"] = "TARGET_HOST_PASS" if all(receipt["checks"].values()) else "BOUNDED_STOP"
receipt["global_stop"] = False
canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
print(json.dumps(receipt, indent=2, sort_keys=True))
PY

python3 - "$EVIDENCE_DIR/cloudworkspace_kind_m3_receipt.json" <<'PY'
import json, sys
receipt=json.load(open(sys.argv[1]))
assert receipt["promotion_state"] == "TARGET_HOST_PASS", receipt
assert receipt["global_stop"] is False
print(json.dumps(receipt, indent=2, sort_keys=True))
PY

info "CloudWorkspaceEngine is running in kind and probe readback passed"
