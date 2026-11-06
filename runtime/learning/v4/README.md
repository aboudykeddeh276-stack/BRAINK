# KS-BRAINK-IL-LLM | V4 observer and bilateral-polygon learning mirror

**Architecture and research:** A. Keddeh, KEDDEH Systems.

This directory preserves `KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html` **byte-for-byte** and adds a minimally instrumented derivative built by `build_v4_host_link.py`. Original V4 contains lexicon, observer formula, bilateral-polygon successor learning and 100-pass routines, but its raw HTML references missing R22 control-wrapper functions. The exact pre-existing V5 Skill Apex supplies those functions in the derivative; the historical V4 is left byte-for-byte unchanged. This bridge is a separate transport and local persistence lane, not a replacement algorithm, agent, consensus implementation or independent server executor.

## Native BRAINK dependencies

* `runtime.illlm_ledger.ILLLMImmutableLedger` (existing persisted, hash-chained ledger).
* `observer2_runtime.kernel.LearningAdmissionGate`, `CandidateState` and `SignalPacket` (existing Observer² contract).
* `aiohttp` for WebSocket/HTTP and Python 3.10+.

No trained model weights, graphical inference backend, ToT quorum, or host pairer is installed by this transport patch. No raw model outputs are promoted to global truth.

## Run on an actual trusted machine

From **BRAINK repository root**:

```bash
python3 -m pip install aiohttp pytest pytest-asyncio
export BRAINK_V4_BRIDGE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export BRAINK_V4_BRIDGE_PORT=8080
export BRAINK_V4_BRIDGE_BIND=127.0.0.1
export BRAINK_V4_LEDGER_PATH="${PWD}/.kex/state/illlm-v4-mirror.jsonl"
python3 -m runtime.learning.v4.host_bridge
```

Navigate to `http://127.0.0.1:8080/v4`. Enter the **environment-issued token manually**, then select **Connect authenticated mirror**. The token is not stored in V4 state. Connections from the served loopback origin are allowed. For KEDDEH.COM origins set an explicit `BRAINK_V4_ALLOWED_ORIGINS` allowlist, provide a TLS/WSS reverse proxy and retain authority scoping; do not publish unauthenticated port 8080 or use public `0.0.0.0` defaults.

`/api/health` reports status, local browser mirror sessions, ledger verification and the preserved source digest. It does **not** report the separately governed broker's external node count. `/api/readback?correlation_id=<64 lowercase hex>` requires `Authorization: Bearer $BRAINK_V4_BRIDGE_TOKEN` and returns persisted source events + independently verified chain status.

## Admission and canonical identities

* WebSocket begins `AUTH`, with unique `instance_id` and a minimum 32-character token. An origin allowlist applies before WebSocket upgrade.
* Only source-matched V4 `STATE_TELEMETRY` events with the **literal V4 observer whole identity and formula** are candidates. Polygon state is captured from V4's actual `S.polygonState` and original `receipt` callbacks, not from invented `currentPolygons` / `observerState.time` variables.
* `LearningAdmissionGate` enforces mirror-only candidates with a bound **real local append-only ledger actuator**. It does not grant server/host execution rights.
* Every appended record has V4 source SHA-256, observer-policy digest, candidate hash, IL-LLM lexical root, durable event root and `promotion_state=NOT_PROMOTED`.
* Origin/credential failure, source mismatch, non-monotonic sequence, malformed observer, oversized message and corrupt ledger fail closed. Browser mirror events are idempotent across reconnect by the original V4 receipt ID and browser instance ID.
* Disconnect/reconnect retains unsent source-observed learning records in V4 localStorage (`S.hostLink.pending`, capped at 1,000). The authoritative content remains in V4. `hostLink` contains no token.
* Heartbeat sweeps expire stale mirror connections; **neither browser count nor healthy localhost reads can manufacture an online external executor**. That requires pairing an actual node with the KEDDEH self-host broker and getting the specified `BOOT_SUBSTRATE` receipt and host heartbeat.

## Validation

```bash
python3 -m pytest -q tests/test_v4_host_bridge.py
python3 runtime/learning/v4/build_v4_host_link.py
```

The tests use real local TCP WebSocket connections, the actual BRAINK IL-LLM ledger API, original Observer² admission classes, independent HTTP readback and durable disk restart. CI uses the existing repo modules. Tests prove the bridge boundary, not site production deployment, global quorum or physical sentience.

## Source and publication boundary

* No existing branch, canonical naming law, ToT replica/mesh, original V4 or site project is overwritten by this patch.
* Once reviewed, launch on a provisioned KEDDEH host and verify `pid → WebSocket AUTH → V4 mirror → ledger fsync → process restart → readback → target host admission → external served-page proof` before claiming production integration.
* ToT convergence requires native voting, independent members, leader coordination and replicated readback beyond this local observer mirror.

## Shared-process persistence admission (concurrent writer closure)

The original ``ILLLMImmutableLedger.append`` could calculate an identical predecessor head in parallel workers and append incompatible records. An actual six-process adversarial run wrote 60 rows but failed chain verification at index 1. This integration includes the same-schema native remedy in ``runtime/illlm_ledger.py``: an OS-backed interprocess lock serializes full-chain verification, predecessor selection, single append/fsync and immediate readback. Shared-lock readbacks reject corrupt/truncated files. The existing SHA-256 event format, canonical architectural identity and strict ``verify_head`` signature remain unchanged.

Actual re-run:

```bash
python -m pytest -q tests/test_illlm_ledger_concurrency.py tests/test_v4_host_bridge.py tests/test_auditable_generation.py
```

**Deployment invariant:** All writers targeting a particular legacy IL-LLM ledger must use this admission lock contract. Unpatched writers bypassing it can still damage the chain. The separate lock inode (``.jsonl.lock``) must not be removed while services run. A local hash chain does not protect against a privileged actor replacing both events and hashes; independent checkpoint/authority readbacks remain required.

## OS process admission and restart readback

A separate test drives the actual CLI process (with an independent PID) over a real loopback TCP connection and sends 100 source-shaped, explicitly TEST_FIXTURE-only transport events. After fsync and health/readback, it kills the original process, starts a fresh process with a distinct PID, and verifies all 100 retained events and the same SHA-256 ledger head. This tests durable transport and process lifecycle, **not** an actual 100-pass V4 browser polygon execution. Browser-navigation attempts in the available execution environment were blocked by administrator policy, so do not promote a V4 end-to-end browser claim.

```bash
python -m pytest -q tests/test_v4_host_process_lifecycle.py
```

## 28 October: real V4 algorithm and V5 R22 source-relink verification

The unchanged V4 references six missing R22 functions. The exact existing V5 Skill Apex source (SHA-256 `ccbaf267a40b3f55b56da6b7f97c77279bdd583d29d1aa27139d085f5acd117b`) supplies the source-exact implementations to `build_v4_host_link.py`. The generator also initializes the mirror observer binding before V5 bootstrap (preventing a JavaScript temporal-dead-zone crash). No new R22 admission law is synthesized.

`node runtime/learning/v4/run_v4_resident.mjs OUTPUT.json STATE.json` runs the **actual original V4 JavaScript polygon and observer functions** together with the V5 R22 wrapper in a native Node process. A minimal document/storage adapter provides the UI-independent execution context and disk-backed local state, **not an actual Chromium DOM**. It executes the native 100-pass routine, produces 100 true V4 `POLYGON_100_ITERATION` receipts plus one `POLYGON_100_COMMIT`, and leaves them as mirror candidates. This does not assert autonomous neural learning or global promotion.

`python runtime/learning/v4/verify_native_v4_100.py /tmp/v4-proof` boots a real aiohttp server on loopback, sends those 101 original-algorithm candidates over an authenticated TCP WebSocket, independently reads them back from the native IL-LLM JSONL file, shuts the listener, constructs a fresh resident bridge object and re-verifies the persisted chain and all 100 successors. Proof is written to `/tmp/v4-proof/v4_100_to_illlm_verification.json`. Only temporary, local execution.

Remaining: actual Chromium UI execution (blocked by browser administrator in this environment), production KEDDEH host pairing (0 registered nodes), GitHub Actions pre-runner failure, and independent physical ToT/mesh quorum. A local Node VM is not a substitute for those boundaries.
