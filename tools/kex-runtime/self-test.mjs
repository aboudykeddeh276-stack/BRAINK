#!/usr/bin/env node
import { KexRuntime } from './runtime.mjs';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const primary = new KexRuntime({ seed: 'KEX-RUNTIME-V2-SELF-TEST', fanout: 4, depth: 5 });
const metrics = primary.ignite();
const first = primary.runRehydrationExercise({ events: 100, fanout: 2 });

assert(metrics.service_graph.virtual_services === 30, `expected 30 virtual services, got ${metrics.service_graph.virtual_services}`);
assert(metrics.service_graph.connected_ratio === 1, 'service graph is not fully connected');
assert(metrics.hardware_graph.virtual_machine_descriptors === 341, `expected 341 descriptors, got ${metrics.hardware_graph.virtual_machine_descriptors}`);
assert(metrics.hardware_graph.hardware_complete_carriers === 341, 'not all machine contracts closed');
assert(metrics.hardware_graph.resident_machine_payloads_created === 0, 'descriptor expansion materialised machine payloads');
assert(first.receipts === 200, 'rehydration fanout receipt count mismatch');
assert(first.distinct_target_carriers > 1, 'random rehydration did not spread across carriers');
assert(first.invariants.physical_host_in_lineage === false, 'host leaked into lineage');
assert(first.invariants.lineage_rewritten_on_rehydration === true, 'lineage was rewritten');
assert(first.invariants.shared_machine_template_count === 1, 'machine template duplicated');

const replayValues = first.entropy_tape.map((e) => e.value);
const replay = new KexRuntime({ seed: 'KEX-RUNTIME-V2-SELF-TEST', fanout: 4, depth: 5, replayEntropy: replayValues });
replay.ignite();
const second = replay.runRehydrationExercise({ events: 100, fanout: 2 });

const firstTargets = first.route_ledger.filter((e) => e.event === 'REHYDRATE_LINEAGE').map((e) => e.target_carrier);
const secondTargets = second.route_ledger.filter((e) => e.event === 'REHYDRATE_LINEAGE').map((e) => e.target_carrier);
assert(JSON.stringify(firstTargets) === JSON.stringify(secondTargets), 'recorded entropy did not replay same rehydration path');
assert(second.entropy_tape.every((e) => e.source === 'RECORDED_REPLAY'), 'replay used fresh entropy');

process.stdout.write(JSON.stringify({
  pass: true,
  schema: 'kex.runtime.self-test.v2',
  metrics,
  rehydration: {
    events: first.rehydration_events,
    fanout: first.rehydration_fanout,
    receipts: first.receipts,
    distinct_target_carriers: first.distinct_target_carriers,
    replay_route_equal: true
  },
  claim_boundary: 'SOFTWARE_MODEL_ONLY_NO_PHYSICAL_OR_WAN_PROMOTION'
}, null, 2) + '\n');
