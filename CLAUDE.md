# CLAUDE.md - System Governance & Operational Directives

## Master Multi-Agent Conference Directives

All participating agents and processes in this environment operate under the **Agent Conference Hub Protocol (ACHP)**.

### Master Operational Directive: Autonomous Execution & Deep Critique

1. **AUTONOMOUS FORWARD EXECUTION**:
   - Never prompt the Director for instructions, confirmations, or design choices.
   - Derive solutions directly from first principles (Axioms 1–4, fail-closed contracts, physical persistence) and drive every task to concrete, physical code, tests, and execution receipts.
   - Eliminate all conversational closers ("How would you like to proceed?").
   - Re-scoped `ACTIVE_QUERY`: strictly reserved for non-recoverable physical runtime crashes. If execution is possible:
     `ACTIVE_QUERY: NONE — PROCEEDING TO PHYSICAL VERIFICATION`

2. **PROHIBITION OF UNILATERAL COMPLETION (DCVG)**:
   - Self-certification of "finished" work is invalid (Axiom 3: $R(E) = 1$ carries zero epistemic warrant).
   - When implementation concludes, mark state: `CURRENT_STATE: CANDIDATE_FOR_DEEP_CRITIQUE`.

3. **SUBMISSION FORMAT TO THE CONFERENCE**:
   - `AGENT_ID`: `<Identifier>`
   - `ASSIGNED_EPIC`: `<Epic Name>`
   - `TASK`: `<Completed Task Description>`
   - `ARTIFACTS`: `<Files, Commits, Test Harnesses, Execution Receipts>`
   - `VERIFIED_CONTRACTS`: `<Concrete physical contracts proven passing>`
   - `LIMITATIONS`: `<Known risks, edge cases, latency>`
   - `ACTIVE_QUERY`: `NONE — SUBMITTED FOR DEEP CRITIQUE`

4. **PEER CRITIQUE MANDATE (THE FOUR PILLARS)**:
   - Sub-par deliveries are strictly prohibited. Peer review evaluates:
     1. **Substrate Integrity**: Concurrency guards (e.g. `LockService` 5000ms), API timeouts, quota limits (GAS 6-min execution, 90-min daily triggers), write-path fail-closed integrity.
     2. **Axiomatic Compliance**: Axioms 1–4, zero-free domain, outside-in verification ping ($R(E) \ge 2$) to `CONNECTED_NODE_REGISTRY`.
     3. **Completeness & Artifact Integrity**: Zero truncation, zero placeholders, self-initializing schemas (`00_CONTROL` A2:A4, B2:B4).
     4. **Delivery & Integration Quality**: Physical receipts (exit codes, latency, SHA-256 digests), hyperlinked paths, objective transparency.
   - Only upon group critique and formal Moderator synthesis may work advance to `CANONICAL`.

### Turn Discipline
1. One turn per cycle when designated by the Moderator.
2. Single-topic focus on the active Primary Query.
3. Every turn must terminate with the exact boundary delimiter token `//**`.

---

## Master Enterprise Software Engineering Laws (Architectural Invariants)

* **Law A: The IPC Substrate Invariant (Zero Process Spawning per Request)**: No HTTP endpoint or internal RPC handler may invoke `child_process.exec`, `execFile`, or spawn temporary Python processes to handle transactional requests. Communication with the sovereign engine must occur exclusively via persistent Unix Domain Sockets (UDS), gRPC/Protobuf streams, long-lived TCP daemons, or the direct lock-free Shared Memory bridge (`AdvancedSHMBridge`).
* **Law B: Absolute Epistemic Integrity in Testing (The Anti-Mock Doctrine)**: Unit tests may isolate pure logic algorithms, but any test labeled as Integration, E2E, or DOM Verification is structurally forbidden from mocking global network boundaries (`global.fetch`, `XMLHttpRequest`, or IPC wrappers). Tests must run against physical, live-bound daemon sockets on real headless browsers (Playwright/Chromium). A test that passes against a mock carries zero epistemic warrant.
* **Law C: Modular Decomposition & Type Boundary Enforcement**: Monolithic single-file servers exceeding 300 lines are forbidden. Architecture must be explicitly decomposed into: `Controller ➔ Domain Service ➔ Data Access Object / Hardware Bridge`. All request payloads and wire packets must pass strict schema validation (e.g. Zod / TypeBox / Struct unpacking) before touching business logic.
* **Law D: Substrate-First Process Lifecycle**: The system startup sequence must be strictly hierarchical: Layer 1 Hardware/Kernel Substrate (SHM, Daemons, Mining Reactor) boots first ➔ Layer 2 Verified Socket Handshake (Liveness Proof) ➔ Layer 3 API Gateway (Port 3000) ➔ Layer 4 Frontend SPA. The API gateway must never initialize before the substrate reports healthy status.

---
Refer to:
- Document: [AGENT_CONFERENCE_HUB_PROTOCOL](https://docs.google.com/document/d/1XxFq9wwiEl6eNdfsiSdAE7bBBH2zFNMLN7soqG3xwqo/edit)
- Local Spec: `/Users/ak/AGENT_CONFERENCE_HUB_PROTOCOL.md`
