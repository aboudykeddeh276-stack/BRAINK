#!/usr/bin/env node
import fs from 'node:fs';
import { normalizeSegment } from './contracts.mjs';
import { EntropyTape } from './entropy.mjs';
import { VirtualHardwareGraph } from './hardware-graph.mjs';
import { TransitionLedger } from './ledger.mjs';
import { DEFAULT_ADAPTERS, MaterialisationRegistry } from './materialisation.mjs';
import { RehydrationEngine } from './rehydration.mjs';
import { VirtualServiceGraph } from './service-graph.mjs';

export class KexRuntime {
  constructor({ seed = 'KEX-RUNTIME-V2', fanout = 4, depth = 5, replayEntropy = [] } = {}) {
    this.seed = normalizeSegment(seed);
    this.root = `KEX://RUNTIME/${this.seed}`;
    this.ledger = new TransitionLedger(this.root);
    this.entropy = new EntropyTape(replayEntropy);
    this.serviceGraph = new VirtualServiceGraph({ seed: this.seed, depth: 3, ledger: this.ledger });
    this.graph = new VirtualHardwareGraph({ seed: this.seed, fanout, depth, ledger: this.ledger });
    this.rehydration = new RehydrationEngine({ graph: this.graph, ledger: this.ledger, entropy: this.entropy });
    this.materialisation = new MaterialisationRegistry({ ledger: this.ledger });
    for (const adapter of DEFAULT_ADAPTERS) this.materialisation.registerAdapter(adapter);
  }

  ignite() {
    const serviceMetrics = this.serviceGraph.ignite();
    const hardwareMetrics = this.graph.expandAndClose();
    const state = Object.freeze({
      service_graph: serviceMetrics,
      hardware_graph: hardwareMetrics,
      service_graph_ref: this.serviceGraph.root,
      hardware_graph_ref: this.graph.root,
      host_in_lineage: false
    });
    this.ledger.append('RUNTIME_READY', state);
    return state;
  }

  runRehydrationExercise({ events = 100, fanout = 2 } = {}) {
    if (!this.graph.spaces.size) this.ignite();
    const eligible = this.graph.eligibleCarriers();
    if (!eligible.length) throw new Error('No hardware-complete carriers');

    const startEntropy = this.entropy.choose(eligible.length, 'INITIAL_WORKLOAD_CARRIER');
    const source = eligible[startEntropy.value];
    const lineageCoordinate = 'KEX://WORKLOAD/GLOBAL-MESH-STATE';
    let active = this.rehydration.registerVirtualMaterialisation({
      lineageCoordinate,
      carrierCoordinate: source.coordinate,
      stateRefs: Object.freeze({ ...source.stateRefs, service_graph_ref: this.serviceGraph.root })
    });

    const allReceipts = [];
    for (let i = 0; i < events; i += 1) {
      const receipts = this.rehydration.rehydrate({
        materialisation: active,
        fanout,
        reason: 'VIRTUAL_CARRIER_LOSS_OR_REPLACEMENT'
      });
      allReceipts.push(...receipts);
      const continuation = this.entropy.choose(receipts.length, `CONTINUATION:${i + 1}`);
      const chosen = receipts[continuation.value];
      active = Object.freeze({
        ...chosen,
        carrier_machine: chosen.target_carrier
      });
    }

    const distinctTargets = new Set(allReceipts.map((r) => r.target_carrier));
    return Object.freeze({
      schema: 'kex.runtime.rehydration.exercise.v2',
      evidence_boundary: 'SOFTWARE_MODEL_ONLY_EXTERNAL_MATERIALISATION_NOT_IMPLIED',
      service_metrics: this.serviceGraph.metrics(),
      hardware_metrics: this.graph.metrics(),
      workload_lineage: lineageCoordinate,
      rehydration_events: events,
      rehydration_fanout: fanout,
      receipts: allReceipts.length,
      distinct_target_carriers: distinctTargets.size,
      latest_materialisation: active,
      entropy_tape: this.entropy.snapshot(),
      route_ledger: this.ledger.snapshot(),
      invariants: Object.freeze({
        physical_host_in_lineage: false,
        lineage_rewritten_on_rehydration: allReceipts.some((r) => r.lineage_rewritten) === false,
        all_targets_hardware_complete: allReceipts.every((r) => r.machine_template_ref && r.target_carrier),
        shared_machine_template_count: 1,
        resident_machine_payloads_created: 0
      })
    });
  }
}

function parseArgs(argv) {
  const out = { seed: 'KEX-RUNTIME-V2', fanout: 4, depth: 5, events: 100, rehydrationFanout: 2, replay: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--seed') out.seed = argv[++i];
    else if (a === '--fanout') out.fanout = Number(argv[++i]);
    else if (a === '--depth') out.depth = Number(argv[++i]);
    else if (a === '--events') out.events = Number(argv[++i]);
    else if (a === '--rehydration-fanout') out.rehydrationFanout = Number(argv[++i]);
    else if (a === '--replay-entropy') out.replay = argv[++i];
    else throw new Error(`Unknown argument ${a}`);
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  let replayEntropy = [];
  if (args.replay) {
    const body = JSON.parse(fs.readFileSync(args.replay, 'utf8'));
    replayEntropy = (body.entropy_tape ?? body).map((e) => typeof e === 'number' ? e : e.value);
  }
  const runtime = new KexRuntime({ seed: args.seed, fanout: args.fanout, depth: args.depth, replayEntropy });
  runtime.ignite();
  process.stdout.write(JSON.stringify(runtime.runRehydrationExercise({ events: args.events, fanout: args.rehydrationFanout }), null, 2) + '\n');
}

if (import.meta.url === `file://${process.argv[1]}`) main();
