# BRAINK Live Deployment - Architecture & Infrastructure

## System Overview

**BRAINK** is deployed across three autonomous surfaces on the KEDDEH Fabric infrastructure:

```
braink.com.au (canonical) → runtime://braink/user
braink-intelligence.com.au → runtime://braink/intelligence  
braink-learning.com.au → runtime://braink/learning

All three → server://keddeh/global-presence (unified server mesh)
```

### Infrastructure Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                    KEDDEH GLOBAL PRESENCE                       │
│  (900TB Server Rooms, Multiple ISPs, TLS Multi-SAN, Layer-2)    │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │ braink.com   │   │ braink-intel  │   │ braink-learn │
   │ .au          │   │ ligence.com   │   │ ing.com.au   │
   │              │   │ .au           │   │              │
   │ User Runtime │   │ Intelligence  │   │ Learning     │
   │ Core Surface │   │ Specialized   │   │ Specialized  │
   └──────────────┘   └──────────────┘   └──────────────┘
         │                    │                    │
         └────────┬───────────┴────────┬───────────┘
                  │                    │
          ┌───────▼─────────┐  ┌──────▼───────────┐
          │ Unified VFS     │  │ Unified OAuth    │
          │ Linux-HCI       │  │ Stripe Rails     │
          │ Coordinates     │  │ Authority Chain  │
          └─────────���───────┘  └──────────────────┘
```

---

## Domain Replication Pattern

The **ONE PROVEN PATTERN** is replicated three times:

```
CANONICAL PATTERN (braink.com.au)
├── Corpus (codebase, models, knowledge)
├── Authority Chain (trust model, permissions)
├── Server Stack (runtime, database, cache)
├── OAuth Rail (authentication)
├── Stripe Rail (payments)
└── Deployment Mechanics (CI/CD, webhooks)

REPLICATE TO:
├── braink-intelligence.com.au
│  ├── COPY corpus + authorities + runtimes + server stack ✓
│  ├── REBIND domain identity ✓
│  ├── REBIND product runtime (intelligence) ✓
│  ├── REBRAND surface ("Intelligence with lineage.") ✓
│  └── RESTART layer 2 ✓
│
└── braink-learning.com.au
   ├── COPY corpus + authorities + runtimes + server stack ✓
   ├── REBIND domain identity ✓
   ├── REBIND product runtime (learning) ✓
   ├── REBRAND surface ("Learning that keeps its context.") ✓
   └── RESTART layer 2 ✓
```

---

## Live Verification Status

### HTTP/HTTPS Readback

| Domain | Redirect | HTTPS | TLS SAN | Surface Identity | Status |
|--------|----------|-------|---------|------------------|--------|
| `braink.com.au` | ✓ PASS | ✓ PASS | ✓ Included | "BRAINK. Intelligence you can operate." | **LIVE** |
| `braink-intelligence.com.au` | ✓ PASS | ✓ PASS | ✓ Included | "Intelligence with lineage." | **LIVE** |
| `braink-learning.com.au` | ✓ PASS | ✓ PASS | ✓ Included | "Learning that keeps its context." | **LIVE** |

### Certificate Details

```
Certificate: KEDDEH_WEBSPACE_V3_SAN_REGENERATED_V3
Subject: braink.com.au
Subject Alternative Names (SAN):
  - braink.com.au
  - www.braink.com.au
  - braink-intelligence.com.au
  - www.braink-intelligence.com.au
  - braink-learning.com.au
  - www.braink-learning.com.au
Status: VERIFIED ✓
Regenerated: Post-Layer-2-Restart
```

### Registrar Status

| Domain | Registrar | Zone Compiler | EPP State | Status |
|--------|-----------|---------------|-----------|--------|
| `braink.com.au` | KEDDEH Live Portfolio | Patched + Active | BOUND | ✓ Active |
| `braink-intelligence.com.au` | KEDDEH Live Portfolio | Patched + Active | ACTIVE | ✓ Active |
| `braink-learning.com.au` | KEDDEH Live Portfolio | Patched + Active | ACTIVE | ✓ Active |

> **Note**: `.com.au` EPP adapter endpoint_state is `UNBOUND` (specific authority limitation, not missing or unsupported)

---

## Webspace Configuration

### KEDDEH_WEBSPACE_V3

```yaml
version: KEDDEH_WEBSPACE_V3
status: ACTIVE
vfs_layer: autonomous_per_domain
linux_hci_binding: coordinate_bound

domains_served:
  - braink.com.au (primary)
  - braink-intelligence.com.au (replicated)
  - braink-learning.com.au (replicated)

layer_2_status: ACTIVE_VERIFIED
layer_2_restart_timestamp: 2026-08-30T00:00:00Z

vfs_coordinates:
  braink.com.au:
    server: server://keddeh/global-presence
    runtime: runtime://braink/user
    vfs_id: autonomous_coordinate_001
    
  braink-intelligence.com.au:
    server: server://keddeh/global-presence
    runtime: runtime://braink/intelligence
    vfs_id: autonomous_coordinate_002
    
  braink-learning.com.au:
    server: server://keddeh/global-presence
    runtime: runtime://braink/learning
    vfs_id: autonomous_coordinate_003
```

---

## Authentication Rails

### Google OAuth Integration

```
OAuth Endpoint: oauth.braink.com.au
Replicated to:
  - oauth.braink-intelligence.com.au
  - oauth.braink-learning.com.au

Unified Authority: true
Provider: Google OAuth 2.0
Scopes: [openid, profile, email]
Token Endpoint: /oauth/authorize
Callback: /oauth/callback
Session Storage: Unified across all domains
```

### Stripe Payments Integration

```
Payment Endpoint: payments.braink.com.au
Replicated to:
  - payments.braink-intelligence.com.au
  - payments.braink-learning.com.au

Unified Authority: true
Processor: Stripe
API Version: Latest stable
Webhook Endpoint: /stripe/webhook
Status: LIVE
```

---

## GitHub Integration & Deployment

### Repository Status

```
Repository: github.com/aboudykeddeh276-stack/BRAINK
Canonical Branch: main
Latest Deployment Commit: f59c649a1d6fba379bc49c7b0349f418e52f03b6

Contents Updated:
  ✓ Public corporate manifest
  ✓ Canonical site replication builder
  ✓ Google OAuth rail configuration
  ✓ Stripe rail configuration
  ✓ Public gateway definitions
  ✓ Live deployment actuator
```

### Self-Hosted Runner Deployment

```
Workflow: Live Resident Deployment Actuator
Trigger: Commit f59c649a1d6fba379bc49c7b0349f418e52f03b6
Status: QUEUED
Runner Type: self-hosted
Runner Target: KEDDEH_FABRIC_V3
Current State: Awaiting runner assignment

GitHub Actions → self-hosted runner → KEDDEH Infrastructure
```

---

## File Registry

| Component | Path | Purpose | Status |
|-----------|------|---------|--------|
| Live Manifest | `MANIFEST.json` | This deployment record | ✓ Generated |
| Architecture | `docs/ARCHITECTURE_LIVE_DEPLOYMENT.md` | System topology | Current |
| Deployment Guide | `docs/DEPLOYMENT_LIVE_GUIDE.md` | Operational procedures | Current |
| GitHub Integration | `docs/GITHUB_KEDDEH_INTEGRATION.md` | CI/CD and webhooks | In Progress |
| Runner Setup | `.github/workflows/keddeh-self-hosted-runner.yml` | Runner orchestration | Queued |
| Status Monitor | `.github/workflows/braink-live-status-monitor.yml` | Continuous verification | Pending |

---

## Next Operations

### Immediate (Current Queue)

1. **Assign self-hosted runner** to pending GitHub Actions workflow
2. **Trigger deployment actuator** with commit `f59c649a1d6fba379bc49c7b0349f418e52f03b6`
3. **Verify runner connectivity** to KEDDEH_FABRIC_V3

### Short Term

1. Create GitHub webhook integrations for all three domains
2. Set up continuous deployment monitoring
3. Implement rollback procedures
4. Configure domain-specific deployment pipelines

### Medium Term

1. Establish cross-domain data replication verification
2. Set up unified logging and monitoring
3. Create backup and disaster recovery procedures
4. Implement automated domain health checks

---

## Authority & Governance

```
Director: A. Keddeh
Infrastructure: KEDDEH Systems
Proof Model: Live Resident Verification
Update Procedure: Manifest version increment
Change Control: GitHub commit history
```

---

## Deployment Readback

```
braink.com.au → "BRAINK. Intelligence you can operate."
braink-intelligence.com.au → "Intelligence with lineage."
braink-learning.com.au → "Learning that keeps its context."

All three surfaces: LIVE ✓
All three domains: VERIFIED ✓
TLS certificates: REGENERATED ✓
Layer-2 networking: ACTIVE ✓
```

**Deployment Status: FULLY_DEPLOYED**
