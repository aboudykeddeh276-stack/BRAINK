# V98 Agent Registry Specification

## 1. Definition

The Agent Registry is the executable control-plane directory for every human authority, coding agent, acceptance agent, virtual CPU executor, virtual GPU projection surface, audit council and VFS custody role operating inside the KEDDEH workstation.

It is not a chatbot list, dashboard decoration, manifest-only report or telemetry substitute. It is a service-discovery, capability-control, authority-boundary and audit-custody registry used by runtime code before an agent may act.

It answers these operational questions:

1. Who or what is this agent?
2. What plane owns it?
3. What actions may it perform?
4. What actions are denied even if requested?
5. What services may it touch?
6. What telemetry does it emit?
7. What receipts must exist before its output can be promoted?

## 2. What it does

The registry prevents orphaned procedures by binding every service, applet, execution path and audit channel to an owner, an input set, an output set, a telemetry surface and a deployment target.

It also prevents authority drift. A coding agent can edit source and create tests. A user can define doctrine and acceptance meaning. A virtual GPU surface can render state. None of those actors can self-promote `LOCAL_PASS`. Only the acceptance harness may promote a local pass after execution, ledger write, ledger readback and handoff.

## 3. Runtime implementation

The registry is implemented through two executable paths:

1. `src/keddeh_agent_registry.py` validates `config/agent_registry.json`, emits `exports/agent_registry_matrix.csv`, writes `evidence/agent_registry_receipt.json`, appends `runtime_volume/proof_bundles.ledger`, verifies readback and emits an outbox handoff.
2. `src/keddeh_agent_runtime_service.py` accepts a concrete work order, authorizes it against the registry, performs a bounded local operation, writes a work-order receipt, appends the ledger, verifies ledger readback and emits an outbox handoff.

The second path is the codeified runtime path. It prevents the registry from being only a manifest.

## 4. User utilization

A user defines the objective and inspects eligible agents. The user does not manually mark a pass state.

```text
objective -> eligible agent -> work order -> runtime authorization -> execution -> receipt -> ledger readback -> outbox handoff
```

## 5. Agent utilization

An agent must resolve its `agent_id`, check the requested action against `allowed_actions` and `denied_actions`, check service binding, then execute only the bounded operation exposed by the runtime service.

Invalid work orders fail closed and still produce receipts so the failed path remains auditable.

## 6. Computer-science abstraction

The Agent Registry maps to:

- identity registry
- RBAC/ABAC policy store
- service-discovery table
- capability registry
- task router
- event-sourced audit plane
- deployment manifest
- finite-state authority boundary

## 7. Virtual CPU and GPU boundary

The virtual CPU plane executes validation, state transitions, service contracts, ledger writes and readbacks.

The virtual GPU plane renders telemetry and dashboard state. It cannot promote correctness and cannot render a pass state into existence.

## 8. Runtime command

```bash
cd v98_protocol_compliance_config
python3 src/keddeh_agent_runtime_service.py --root . --agent-id acceptance_harness_agent --action write_receipt --service-id agent_registry_service --payload-json '{"manual":"false"}' --emit-receipt
python3 -m unittest tests.test_agent_runtime_service -v
```
