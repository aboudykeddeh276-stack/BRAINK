# V98 Agent Registry Specification

## 1. Definition

The Agent Registry is the machine-readable control-plane directory for every human authority, coding agent, acceptance agent, virtual CPU executor, virtual GPU projection surface, audit council and VFS custody role operating inside the KEDDEH workstation.

It is not a chatbot list and not a dashboard decoration. It is a service-discovery, capability-control, authority-boundary and audit-custody registry. It answers five operational questions before an agent may act:

1. Who or what is this agent?
2. What plane owns it?
3. What actions may it perform?
4. What actions are denied even if requested?
5. What receipts must exist before its output can be promoted?

## 2. What it does

The registry prevents orphaned procedures by binding every service, applet, execution path and audit channel to an owner, an input set, an output set, a telemetry surface and a deployment target.

It also prevents authority drift. A coding agent can edit source and create tests. A user can define doctrine and acceptance meaning. A virtual GPU surface can render state. None of those actors can self-promote LOCAL_PASS. Only the acceptance harness may promote a local pass after execution, ledger write, ledger readback and handoff.

## 3. How it does it

The registry is implemented as `config/agent_registry.json` and validated by `src/keddeh_agent_registry.py`.

The validator enforces:

- all required fields are present
- every agent has explicit allowed and denied actions
- no non-acceptance agent has promotion authority
- telemetry is declared as observation, not proof
- virtual GPU agents render but do not certify
- every service binding is explicit
- the registry writes a receipt, verifies ledger readback and emits an outbox handoff

## 4. User utilisation

A user uses the registry through the workstation dashboard, CLI or deployment runbook. The user does not manually mark agents as successful. The user defines or changes the desired architecture, assigns work to an agent type, and then reads the produced state:

```text
select objective -> view eligible agents -> assign work -> run acceptance -> inspect receipts -> handoff package
```

For example, a user can assign a repository implementation task to `codex_implementation_agent`, but the work is not accepted until `acceptance_harness_agent` executes and emits a receipt.

## 5. Agent utilisation

An agent uses the registry as its permission and routing manifest. Before acting, the agent reads its `agent_id`, `allowed_actions`, `denied_actions`, `service_bindings`, inputs and outputs. If the requested action is denied or unlisted, the correct result is rejection or escalation, not improvisation.

## 6. Deployment

The registry deploys with V98 under:

```text
v98_protocol_compliance_config/config/agent_registry.json
v98_protocol_compliance_config/src/keddeh_agent_registry.py
v98_protocol_compliance_config/tests/test_agent_registry.py
```

It is executed by:

```bash
python3 src/keddeh_agent_registry.py --root . --emit-receipt
```

The output artifacts are:

```text
evidence/agent_registry_receipt.json
exports/agent_registry_matrix.csv
runtime_volume/proof_bundles.ledger
runtime_volume/outbox/agent_registry/*.handoff.json
```

## 7. Governing frameworks

The registry maps to software lifecycle governance, secure development, AI governance, security verification, observability and supply-chain control. It remains reference-alignment unless a qualified external assessment or certificate exists.

The practical governance model is:

- ISO/IEC/IEEE 12207 for software life-cycle process framing
- ISO/IEC 42001 and ISO/IEC 23894 for AI-management and AI-risk framing
- ISO/IEC 27001/27002 and NIST SSDF for security control and secure-development framing
- OWASP ASVS for application security verification requirements
- SLSA and CycloneDX for supply-chain and software-bill-of-materials framing
- OpenTelemetry for traces, metrics, logs and runtime observability

## 8. Processes powering capability

The registry is powered by five process families:

1. Identity binding: agent identity, role, plane and deployment target.
2. Capability binding: allowed actions, denied actions and service bindings.
3. Lifecycle enforcement: recognize, execute, verify, write_receipt, readback and handoff.
4. Observability: traces, metrics, logs, audit events and UI render events.
5. Custody: append-only ledger entry, readback, outbox handoff and target-host gates.

## 9. Real-world computer science abstraction

In conventional terms, the Agent Registry is a combination of:

- identity registry
- capability registry
- RBAC/ABAC policy map
- service-discovery table
- task router
- control plane
- event-sourced audit log
- observability configuration
- deployment manifest
- finite-state-machine authority boundary

Its purpose is to make agentic work mechanically attributable, governable, inspectable and deployable.
