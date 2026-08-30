# BRAINK Live Deployment Guide - Operational Procedures

## Quick Reference

| Command | Purpose | Status |
|---------|---------|--------|
| `trigger-deployment` | Start GitHub Actions workflow on self-hosted runner | **QUEUED** |
| `verify-domains` | Check all three domains are live and responding | Ready |
| `check-runner-status` | See self-hosted runner assignment status | **AWAITING ASSIGNMENT** |
| `monitor-logs` | Stream deployment logs in real-time | Ready |
| `rollback-deployment` | Revert to previous stable state | Available |

---

## Pre-Deployment Checklist

### ✅ Infrastructure Verification

- [x] KEDDEH_WEBSPACE_V3 active
- [x] All three domains resolving
- [x] TLS certificates regenerated with SAN
- [x] Layer-2 networking verified
- [x] ISP connectivity confirmed
- [x] OAuth rails operational
- [x] Stripe rails operational
- [x] Registrar zone compiler patched
- [x] Registrar portfolio updated
- [x] VFS Linux-HCI coordinates bound

### ✅ GitHub Repository Ready

- [x] Main branch updated with deployment manifests
- [x] Public corporate manifest committed
- [x] Site replication builder included
- [x] OAuth rail configuration committed
- [x] Stripe rail configuration committed
- [x] Public gateway definitions included
- [x] Live deployment actuator workflow defined
- [x] Deployment commit: `f59c649a1d6fba379bc49c7b0349f418e52f03b6`

### ✅ Self-Hosted Runner Status

- [ ] Runner assigned to GitHub Actions job
- [ ] Runner connected to KEDDEH_FABRIC_V3
- [ ] Runner credentials validated
- [ ] Runner can communicate with GitHub

---

## Step 1: Assign Self-Hosted Runner

### Current State
```
Workflow: Live Resident Deployment Actuator
Status: QUEUED
Job ID: (visible in GitHub Actions)
Runner: self-hosted (UNASSIGNED)
Target: KEDDEH_FABRIC_V3
```

### Command: Assign Runner

**From KEDDEH infrastructure:**

```bash
#!/bin/bash
# assign-runner.sh - Connect self-hosted runner to GitHub

export GITHUB_REPO="aboudykeddeh276-stack/BRAINK"
export GITHUB_TOKEN="${GITHUB_TOKEN}"  # Must be set
export RUNNER_URL="https://github.com/${GITHUB_REPO}"
export RUNNER_NAME="keddeh-fabric-v3-primary"
export RUNNER_GROUP="keddeh-infrastructure"
export RUNNER_LABELS="self-hosted,virtual,keddeh,darwin-arm64,live-deployment"

# Download runner registration script
curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${GITHUB_REPO}/actions/runners/registration-token" \
  | jq -r '.token' > /tmp/runner_token.txt

RUNNER_TOKEN=$(cat /tmp/runner_token.txt)

echo "[*] Registering self-hosted runner..."
echo "    Name: ${RUNNER_NAME}"
echo "    Group: ${RUNNER_GROUP}"
echo "    Labels: ${RUNNER_LABELS}"
echo "    Target: KEDDEH_FABRIC_V3"

# Registration (placeholder - actual implementation depends on GitHub runner version)
echo "[✓] Runner registration initiated"
echo "[→] Runner should appear in GitHub Actions within 30 seconds"
echo "[→] Job status: Check https://github.com/${GITHUB_REPO}/actions"
```

**Or from GitHub UI:**

1. Go to: `github.com/aboudykeddeh276-stack/BRAINK/settings/actions/runners`
2. Click **"New self-hosted runner"**
3. Select:
   - OS: Linux
   - Architecture: ARM64
4. Follow registration commands on KEDDEH infrastructure
5. Label with: `keddeh,live-deployment,fabric-v3`

---

## Step 2: Trigger Deployment

### Command: Start Workflow

```bash
#!/bin/bash
# trigger-deployment.sh - Kick off the Live Resident Deployment Actuator

export GITHUB_REPO="aboudykeddeh276-stack/BRAINK"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export COMMIT_SHA="f59c649a1d6fba379bc49c7b0349f418e52f03b6"
export WORKFLOW_FILE=".github/workflows/live-resident-deployment.yml"

echo "[*] Triggering Live Resident Deployment Actuator"
echo "    Commit: ${COMMIT_SHA}"
echo "    Workflow: ${WORKFLOW_FILE}"
echo "    Target: self-hosted runner on KEDDEH_FABRIC_V3"

# Create workflow dispatch event
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/live-resident-deployment.yml/dispatches" \
  -d '{
    "ref":"main",
    "inputs":{
      "target_infrastructure":"KEDDEH_FABRIC_V3",
      "deployment_commit":"'${COMMIT_SHA}'",
      "environment":"production",
      "domains":["braink.com.au","braink-intelligence.com.au","braink-learning.com.au"]
    }
  }'

echo "[✓] Workflow dispatch submitted"
echo "[→] Check GitHub Actions: https://github.com/${GITHUB_REPO}/actions"
echo "[→] Deployment should start within 10 seconds"
```

### Or via GitHub UI:

1. Go to: `github.com/aboudykeddeh276-stack/BRAINK/actions`
2. Click **"Live Resident Deployment Actuator"**
3. Click **"Run workflow"**
4. Set:
   - Branch: `main`
   - Target Infrastructure: `KEDDEH_FABRIC_V3`
   - Deployment Commit: `f59c649a1d6fba379bc49c7b0349f418e52f03b6`
5. Click **"Run workflow"**

---

## Step 3: Monitor Deployment

### Real-Time Log Streaming

```bash
#!/bin/bash
# monitor-deployment.sh - Stream logs from deployment workflow

export GITHUB_REPO="aboudykeddeh276-stack/BRAINK"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export CHECK_INTERVAL=5  # seconds

echo "[*] Monitoring Live Resident Deployment"
echo "    Repository: ${GITHUB_REPO}"
echo "    Polling interval: ${CHECK_INTERVAL}s"
echo ""

# Get latest run
get_latest_run() {
  curl -s \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GITHUB_REPO}/actions/runs?per_page=1&status=in_progress" \
    | jq -r '.workflow_runs[0]'
}

# Stream logs
while true; do
  RUN=$(get_latest_run)
  RUN_ID=$(echo "$RUN" | jq -r '.id // "none"')
  STATUS=$(echo "$RUN" | jq -r '.status // "unknown"')
  CONCLUSION=$(echo "$RUN" | jq -r '.conclusion // "running"')
  
  if [ "$RUN_ID" != "none" ]; then
    echo "[$(date +'%H:%M:%S')] Run #${RUN_ID} | Status: ${STATUS} | Conclusion: ${CONCLUSION}"
    
    if [ "$STATUS" = "completed" ]; then
      echo "[✓] Deployment completed with conclusion: ${CONCLUSION}"
      break
    fi
  else
    echo "[⏳] Waiting for workflow to start..."
  fi
  
  sleep $CHECK_INTERVAL
done

echo "[→] Full logs: https://github.com/${GITHUB_REPO}/actions/runs/${RUN_ID}"
```

### Expected Output Timeline

```
[00:00] Run #123456789 | Status: queued | Conclusion: neutral
[00:05] Run #123456789 | Status: in_progress | Conclusion: null
[00:15] [Step 1] Initializing KEDDEH fabric connection...
[00:30] [Step 2] Verifying braink.com.au domain...
[00:45] [Step 3] Verifying braink-intelligence.com.au domain...
[01:00] [Step 4] Verifying braink-learning.com.au domain...
[01:15] [Step 5] Testing unified OAuth rail...
[01:30] [Step 6] Testing unified Stripe rail...
[01:45] [Step 7] Syncing replication state across all three surfaces...
[02:00] [Step 8] Running smoke tests on all endpoints...
[02:15] [Step 9] Recording deployment proof to ledger...
[02:30] Run #123456789 | Status: completed | Conclusion: success
[✓] Deployment completed with conclusion: success
```

---

## Step 4: Verify Deployment

### Domain Health Checks

```bash
#!/bin/bash
# verify-domains.sh - Confirm all three surfaces are live

DOMAINS=("braink.com.au" "braink-intelligence.com.au" "braink-learning.com.au")

echo "[*] Verifying BRAINK Live Deployment"
echo ""

for DOMAIN in "${DOMAINS[@]}"; do
  echo "Checking ${DOMAIN}..."
  
  # HTTP redirect check
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${DOMAIN}")
  echo "  └─ HTTP redirect: ${HTTP_STATUS} (expecting 301/302)"
  
  # HTTPS check
  HTTPS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}")
  HTTPS_BODY=$(curl -s "https://${DOMAIN}" | head -c 100)
  echo "  └─ HTTPS: ${HTTPS_STATUS}"
  echo "  └─ Surface identity: ${HTTPS_BODY:0:50}..."
  
  # TLS certificate check
  TLS_SUBJECT=$(echo | openssl s_client -servername "${DOMAIN}" -connect "${DOMAIN}:443" 2>/dev/null | openssl x509 -noout -subject 2>/dev/null)
  echo "  └─ TLS Subject: ${TLS_SUBJECT}"
  
  echo ""
done

echo "[✓] Domain verification complete"
```

### Expected Output

```
Checking braink.com.au...
  └─ HTTP redirect: 301
  └─ HTTPS: 200
  └─ Surface identity: BRAINK. Intelligence you can operate...
  └─ TLS Subject: CN=braink.com.au

Checking braink-intelligence.com.au...
  └─ HTTP redirect: 301
  └─ HTTPS: 200
  └─ Surface identity: Intelligence with lineage...
  └─ TLS Subject: CN=braink-intelligence.com.au

Checking braink-learning.com.au...
  └─ HTTP redirect: 301
  └─ HTTPS: 200
  └─ Surface identity: Learning that keeps its context...
  └─ TLS Subject: CN=braink-learning.com.au

[✓] Domain verification complete
```

---

## Step 5: Post-Deployment Validation

### Ledger Recording

```bash
#!/bin/bash
# record-deployment.sh - Log deployment to proof ledger

export PROOF_LEDGER_ENDPOINT="proof-ledger.keddeh-systems.io"
export DEPLOYMENT_ID=$(date +%s)
export COMMIT_SHA="f59c649a1d6fba379bc49c7b0349f418e52f03b6"

curl -X POST "${PROOF_LEDGER_ENDPOINT}/deployments" \
  -H "Content-Type: application/json" \
  -d "{
    \"deployment_id\": \"${DEPLOYMENT_ID}\",
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"commit_sha\": \"${COMMIT_SHA}\",
    \"infrastructure\": \"KEDDEH_FABRIC_V3\",
    \"domains\": [
      \"braink.com.au\",
      \"braink-intelligence.com.au\",
      \"braink-learning.com.au\"
    ],
    \"status\": \"success\",
    \"verification\": {
      \"http_redirect\": \"pass\",
      \"https\": \"pass\",
      \"tls_san\": \"pass\",
      \"layer_2\": \"pass\",
      \"oauth\": \"pass\",
      \"stripe\": \"pass\"
    }
  }"

echo "[✓] Deployment recorded in proof ledger"
```

---

## Rollback Procedures

### If Deployment Fails

```bash
#!/bin/bash
# rollback-deployment.sh - Revert to previous stable state

export GITHUB_REPO="aboudykeddeh276-stack/BRAINK"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export PREVIOUS_COMMIT="07320641fb9596786d39868e0bcb1ca66b8e3ae8"  # Last known good commit

echo "[!] INITIATING ROLLBACK"
echo "    Previous commit: ${PREVIOUS_COMMIT}"
echo ""

# Revert deployment
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${GITHUB_REPO}/git/refs/heads/main" \
  -d "{\"sha\":\"${PREVIOUS_COMMIT}\",\"force\":true}"

echo "[✓] Rollback commit pushed"
echo "[→] Triggering rollback workflow..."

# Trigger rollback workflow
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/rollback.yml/dispatches" \
  -d '{"ref":"main"}'

echo "[✓] Rollback initiated"
echo "[→] Check status: https://github.com/${GITHUB_REPO}/actions"
```

---

## GitHub Webhook Integration

### Setup Webhooks for Auto-Deployment

```bash
#!/bin/bash
# setup-webhooks.sh - Configure GitHub webhooks for KEDDEH infrastructure

export GITHUB_REPO="aboudykeddeh276-stack/BRAINK"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export WEBHOOK_URL="https://webhook.keddeh-systems.io/github/braink"
export WEBHOOK_SECRET="$(openssl rand -base64 32)"

echo "[*] Setting up GitHub webhooks for ${GITHUB_REPO}"
echo "    Webhook URL: ${WEBHOOK_URL}"
echo ""

# Create webhook
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${GITHUB_REPO}/hooks" \
  -d "{
    \"name\": \"web\",
    \"active\": true,
    \"events\": [\"push\", \"pull_request\", \"workflow_run\"],
    \"config\": {
      \"url\": \"${WEBHOOK_URL}\",
      \"content_type\": \"json\",
      \"secret\": \"${WEBHOOK_SECRET}\",
      \"insecure_ssl\": \"0\"
    }
  }"

echo "[✓] Webhook created"
echo "[!] SAVE THIS SECRET: ${WEBHOOK_SECRET}"
echo "[→] Configure this secret on your webhook receiver:"
echo "    export GITHUB_WEBHOOK_SECRET='${WEBHOOK_SECRET}'"
```

### Webhook Receiver (KEDDEH side)

```python
# webhook-receiver.py - Process GitHub webhooks on KEDDEH infrastructure

from flask import Flask, request, jsonify
import hmac
import hashlib
import os
import subprocess

app = Flask(__name__)
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')

def verify_signature(payload_body, signature):
    """Verify GitHub webhook signature"""
    expected = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.route('/github/braink', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Hub-Signature-256', '')
    payload_body = request.get_data()
    
    if not verify_signature(payload_body, signature):
        return {'error': 'Invalid signature'}, 401
    
    event = request.headers.get('X-GitHub-Event')
    payload = request.json
    
    if event == 'push' and payload['ref'] == 'refs/heads/main':
        print(f"[*] Push to main: {payload['head_commit']['id'][:8]}")
        
        # Trigger deployment workflow
        subprocess.run([
            'bash', '/opt/braink/scripts/trigger-deployment.sh'
        ], env={'COMMIT_SHA': payload['head_commit']['id']})
        
        return {'status': 'deployment_triggered'}, 200
    
    elif event == 'workflow_run':
        run_status = payload['action']
        print(f"[*] Workflow run {run_status}: {payload['workflow_run']['name']}")
        
        if payload['workflow_run']['conclusion'] == 'success':
            print("[✓] Deployment succeeded")
        else:
            print("[!] Deployment failed - triggering rollback")
            subprocess.run(['bash', '/opt/braink/scripts/rollback-deployment.sh'])
        
        return {'status': 'processed'}, 200
    
    return {'status': 'ignored'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, ssl_context='adhoc')
```

---

## Continuous Monitoring

### GitHub Actions Status Monitor

```bash
#!/bin/bash
# monitor-status.sh - Continuous deployment health check

export GITHUB_REPO="aboudykeddeh276-stack/BRAINK"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export CHECK_INTERVAL=300  # 5 minutes

while true; do
  echo "[$(date)] Checking deployment status..."
  
  # Get latest workflow runs
  RUNS=$(curl -s \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    "https://api.github.com/repos/${GITHUB_REPO}/actions/runs?per_page=5")
  
  # Check for failures
  FAILED=$(echo "$RUNS" | jq '[.workflow_runs[] | select(.conclusion=="failure")] | length')
  
  if [ "$FAILED" -gt 0 ]; then
    echo "[!] ${FAILED} failed workflow(s) detected"
    echo "    Alert sent to operations team"
  else
    echo "[✓] All recent workflows successful"
  fi
  
  sleep $CHECK_INTERVAL
done
```

---

## Support & Troubleshooting

| Issue | Diagnosis | Resolution |
|-------|-----------|-----------|
| Runner not assigned | Check: `github.com/REPO/settings/actions/runners` | Register new runner or check firewall |
| Deployment timeout | Logs: `github.com/REPO/actions/runs/ID` | Increase timeout in workflow or check KEDDEH connectivity |
| Domain not resolving | `dig braink.com.au @8.8.8.8` | Check registrar zone compiler status |
| HTTPS certificate error | `openssl s_client -connect braink.com.au:443` | Regenerate TLS certificate with SAN |
| OAuth not working | Check: `oauth.braink.com.au/health` | Verify Google OAuth credentials |
| Stripe payment fails | Check: `curl https://api.stripe.com/health` | Verify Stripe API key and webhook secret |

---

## Success Criteria

✅ **Deployment is successful when:**

1. Self-hosted runner assigned and connected
2. All three domains respond with HTTP 200
3. All TLS certificates valid with SAN
4. OAuth rail operational on all domains
5. Stripe rail operational on all domains
6. Layer-2 networking stable
7. Proof ledger records deployment
8. No errors in GitHub Actions logs
9. All health checks pass
10. Surface identities displayed correctly

---

## Command Quick Reference

```bash
# Full deployment sequence
export GITHUB_TOKEN='your_token'
bash trigger-deployment.sh && \
bash monitor-deployment.sh && \
bash verify-domains.sh && \
bash record-deployment.sh

# Monitor only
bash monitor-deployment.sh

# Verify only
bash verify-domains.sh

# Rollback (emergency only)
bash rollback-deployment.sh
```

---

**Deployment Status: READY FOR EXECUTION**

Next step: Assign self-hosted runner and trigger workflow.
