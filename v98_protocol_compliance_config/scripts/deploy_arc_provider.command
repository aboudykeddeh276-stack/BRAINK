#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VALUES="$ROOT/deploy/arc/keddeh-arc-runner-set.values.yaml"
GITHUB_CONFIG_URL="${GITHUB_CONFIG_URL:-https://github.com/aboudykeddeh276-stack/BRAINK}"
CONTROLLER_NAMESPACE="${CONTROLLER_NAMESPACE:-arc-systems}"
RUNNER_NAMESPACE="${RUNNER_NAMESPACE:-arc-runners}"
CONTROLLER_RELEASE="${CONTROLLER_RELEASE:-keddeh-arc-controller}"
RUNNER_RELEASE="${RUNNER_RELEASE:-keddeh-arc-runner-set}"

for command in kubectl helm; do
  command -v "$command" >/dev/null || { echo "missing required command: $command" >&2; exit 2; }
done

if [[ -z "${GITHUB_PAT:-}" && -z "${GITHUB_APP_ID:-}" ]]; then
  echo "Set GITHUB_PAT or GitHub App credentials before deploying ARC." >&2
  exit 3
fi

helm upgrade --install "$CONTROLLER_RELEASE" \
  --namespace "$CONTROLLER_NAMESPACE" \
  --create-namespace \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller

kubectl create namespace "$RUNNER_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

if [[ -n "${GITHUB_PAT:-}" ]]; then
  kubectl -n "$RUNNER_NAMESPACE" create secret generic keddeh-arc-github-auth \
    --from-literal=github_token="$GITHUB_PAT" \
    --dry-run=client -o yaml | kubectl apply -f -
else
  : "${GITHUB_APP_INSTALLATION_ID:?GITHUB_APP_INSTALLATION_ID is required}"
  : "${GITHUB_APP_PRIVATE_KEY_FILE:?GITHUB_APP_PRIVATE_KEY_FILE is required}"
  kubectl -n "$RUNNER_NAMESPACE" create secret generic keddeh-arc-github-auth \
    --from-literal=github_app_id="$GITHUB_APP_ID" \
    --from-literal=github_app_installation_id="$GITHUB_APP_INSTALLATION_ID" \
    --from-file=github_app_private_key="$GITHUB_APP_PRIVATE_KEY_FILE" \
    --dry-run=client -o yaml | kubectl apply -f -
fi

helm upgrade --install "$RUNNER_RELEASE" \
  --namespace "$RUNNER_NAMESPACE" \
  --create-namespace \
  --set githubConfigUrl="$GITHUB_CONFIG_URL" \
  -f "$VALUES" \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set

kubectl wait --for=condition=Ready pod \
  --selector=app.kubernetes.io/instance="$RUNNER_RELEASE" \
  --namespace "$RUNNER_NAMESPACE" \
  --timeout=300s || true

kubectl get pods -n "$CONTROLLER_NAMESPACE"
kubectl get pods -n "$RUNNER_NAMESPACE"

mkdir -p "$ROOT/evidence"
python3 - "$ROOT/evidence/arc_provider_deployment_receipt.json" "$GITHUB_CONFIG_URL" "$RUNNER_RELEASE" <<'PY'
import json, subprocess, sys, time
from pathlib import Path
path, url, release = sys.argv[1:]
def output(*args):
    return subprocess.check_output(args, text=True).strip()
payload = {
    "provider_id": "provider://kubernetes/arc",
    "github_config_url": url,
    "runner_scale_set": release,
    "controller_pods": output("kubectl", "get", "pods", "-n", "arc-systems", "-o", "json"),
    "runner_pods": output("kubectl", "get", "pods", "-n", "arc-runners", "-o", "json"),
    "promotion_state": "PROVIDER_OBSERVED",
    "global_stop": False,
    "observed_at": time.time(),
}
Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

echo "ARC provider deployed; receipt: $ROOT/evidence/arc_provider_deployment_receipt.json"
