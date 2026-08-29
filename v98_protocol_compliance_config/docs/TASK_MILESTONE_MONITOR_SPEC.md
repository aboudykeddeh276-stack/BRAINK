# V98 Task Milestone Monitor Specification

## 1. Purpose

The task milestone monitor converts the instruction "check in every 50 completed tasks across the next 100 tasks" into executable software.

It does not count claims, manifests, telemetry-only events, hashes, or report text as completed work. It counts only completion records that are tied to an existing receipt file and an allowed completion state.

## 2. What it does

The monitor expands `config/task_milestone_registry.json` into exactly 100 task slots across ten worker lanes. Each lane binds a task group to a worker agent, service, standard anchor, deployment boundary and receipt requirement.

It then reads `runtime_volume/task_completion_records.json`, validates each completion record, writes a CSV matrix, appends a ledger entry, verifies readback, writes an evidence receipt, and emits an outbox handoff.

When the valid receipt-backed completion count first reaches 50 or 100, the monitor marks `notify_required=true` and emits a milestone case study payload.

## 3. How a worker records task completion

A worker must attach a real receipt path:

```bash
python3 src/keddeh_task_milestone_monitor.py \
  --root . \
  --record-task V98-G01_protocol_compliance-001 \
  --receipt-path evidence/some_receipt.json \
  --completed-by acceptance_harness_agent \
  --emit-receipt
```

The record is rejected if the receipt does not exist, if the state is not promotable, if the record uses a hash as functional proof, or if it is telemetry-only.

## 4. How a user uses it

The user runs:

```bash
bash scripts/task_milestones.command
```

Then reviews:

- `evidence/task_milestone_monitor_receipt.json`
- `exports/task_milestone_matrix.csv`
- `runtime_volume/proof_bundles.ledger`
- `runtime_volume/outbox/task_milestones/*.handoff.json`

## 5. How an agent uses it

An agent records only its assigned task after generating a concrete receipt. The monitor validates the record against the task registry and does not allow the agent to self-promote a task without receipt-backed evidence.

## 6. Worker case-study fields

At 50 and 100 completed tasks, the monitor emits a case study containing:

- trajectory
- useful growth
- environment relevance
- capacity adequacy
- logical progression
- unmet needs
- standards basis
- next actions

## 7. Real-world computer science abstraction

The monitor is a bounded progress-control system. It combines:

- event-sourced task completion
- receipt-backed state transition
- milestone threshold detection
- service registry integration
- audit ledger append/readback
- workflow handoff
- failed-closed validation

It is not a project-management decoration. It is a state machine for proving that work moved from planned to executed through evidence.
