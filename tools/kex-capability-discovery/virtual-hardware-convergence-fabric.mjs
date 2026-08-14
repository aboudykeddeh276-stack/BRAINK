#!/usr/bin/env node
import crypto from 'node:crypto';
import fs from 'node:fs';

const HARDWARE_CONTRACT = Object.freeze({
  CPU: ['ISA','REGISTER_FILE','PRIVILEGE','EXECUTION'],
  MMU: ['ADDRESS_SPACE','PAGE_TABLE','TRANSLATION','PROTECTION'],
  MEMORY: ['RAM','ROM','NUMA_DESCRIPTOR','SNAPSHOT'],
  SYSTEM_BUS: ['MMIO','PORT_IO','ADDRESS_DECODE','HOTPLUG'],
  DMA_IOMMU: ['DMA','IOMMU','DEVICE_MEMORY_MAP'],
  INTERRUPT: ['IRQ_CONTROLLER','VECTOR_TABLE','ROUTING'],
  TIMER_CLOCK: ['MONOTONIC_CLOCK','TIMER','RTC','WATCHDOG'],
  NETWORK: ['VNIC','QUEUE','LINK_STATE','ROUTE_BINDING'],
  BLOCK: ['VBLOCK','NAMESPACE','SNAPSHOT','JOURNAL'],
  FIRMWARE: ['BOOT_ROM','NVRAM','DEVICE_TREE_OR_ACPI'],
  BOOT: ['LOADER','KERNEL_HANDOFF','INIT_STATE'],
  CONSOLE_DISPLAY: ['SERIAL','FRAMEBUFFER','INPUT'],
  ACCELERATOR: ['VECTOR','GPU_DESCRIPTOR','OFFLOAD_CONTRACT'],
  ENTROPY: ['RNG_INTERFACE','ENTROPY_STATE']
});

const REQUIRED_FAMILIES = Object.freeze(Object.keys(HARDWARE_CONTRACT));
const MACHINE_TEMPLATE_COORDINATE = 'KEX://MACHINE-TEMPLATE/HYPERPROCESSOR-V1';

function seg(v) {
  return String(v).trim().replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'STATE';
}

class Ledger {
  constructor(root) { this.root = root; this.events = []; }
  append(event, payload = {}) {
    const row = Object.freeze({ seq: this.events.length + 1, event, lineage_root: this.root, ...payload });
    this.events.push(row);
    return row;
  }
}

class EntropyTape {
  constructor(replay = []) { this.replay = [...replay]; this.cursor = 0; this.recorded = []; }
  index(maxExclusive, label) {
    if (!Number.isInteger(maxExclusive) || maxExclusive < 1) throw new Error(`Invalid entropy range for ${label}`);
    let value;
    let source;
    if (this.cursor < this.replay.length) {
      value = Number(this.replay[this.cursor++]);
      if (!Number.isInteger(value) || value < 0 || value >= maxExclusive) {
        throw new Error(`Replay entropy ${value} invalid for range 0..${maxExclusive - 1} (${label})`);
      }
      source = 'RECORDED_REPLAY';
    } else {
      value = crypto.randomInt(maxExclusive);
      source = 'OS_CSPRNG';
    }
    const observation = Object.freeze({ label, range: maxExclusive, value, source });
    this.recorded.push(observation);
    return observation;
  }
}

class MachineTemplate {
  constructor() {
    this.coordinate = MACHINE_TEMPLATE_COORDINATE;
    this.families = HARDWARE_CONTRACT;
    this.requiredFamilies = REQUIRED_FAMILIES;
    this.role = 'INVARIANT_GENERATOR';
    this.physical_performance_claim = false;
  }

  completeness(capabilities) {
    const present = this.requiredFamilies.filter((f) => capabilities.has(f));
    return Object.freeze({ present: present.length, required: this.requiredFamilies.length, ratio: present.length / this.requiredFamilies.length, complete: present.length === this.requiredFamilies.length });
  }
}

class VirtualMachineSpace {
  constructor({ coordinate, lineageRoot, parentCarrier, generation, template }) {
    this.coordinate = coordinate;
    this.lineageRoot = lineageRoot;
    this.parentCarrier = parentCarrier;
    this.generation = generation;
    this.templateRef = template.coordinate;
    this.capabilities = new Set(template.requiredFamilies);
    this.machineState = Object.freeze({
      cpu_state_ref: `${coordinate}/STATE/CPU`,
      memory_state_ref: `${coordinate}/STATE/MEMORY`,
      device_graph_ref: `${coordinate}/STATE/DEVICES`,
      interrupt_state_ref: `${coordinate}/STATE/IRQ`,
      boot_state_ref: `${coordinate}/STATE/BOOT`,
      network_state_ref: `${coordinate}/STATE/NETWORK`,
      storage_state_ref: `${coordinate}/STATE/BLOCK`
    });
    this.hardware = template.completeness(this.capabilities);
    if (!this.hardware.complete) throw new Error(`${coordinate}: incomplete machine contract`);
  }

  descriptor() {
    return Object.freeze({
      coordinate: this.coordinate,
      lineage_root: this.lineageRoot,
      parent_virtual_carrier: this.parentCarrier,
      generation: this.generation,
      machine_template_ref: this.templateRef,
      hardware_contract: this.hardware,
      machine_state: this.machineState,
      state: 'VIRTUAL_BARE_METAL_ADDRESSABLE',
      physical_performance_equivalence_claim: false
    });
  }
}

class VirtualHardwareFabric {
  constructor({ seed = 'KEX-HARDWARE-MESH-V1', fanout = 4, depth = 4, replayEntropy = [] } = {}) {
    if (!Number.isInteger(fanout) || fanout < 1 || fanout > 32) throw new Error('fanout must be 1..32');
    if (!Number.isInteger(depth) || depth < 1 || depth > 8) throw new Error('depth must be 1..8');
    this.seed = seg(seed);
    this.virtualRoot = `KEX://HARDWARE-MESH/${this.seed}`;
    this.template = new MachineTemplate();
    this.ledger = new Ledger(this.virtualRoot);
    this.entropy = new EntropyTape(replayEntropy);
    this.spaces = new Map();
    this.materialisations = new Map();
    this.fanout = fanout;
    this.depth = depth;
    this.hostEnvelope = Object.freeze({ boundary: 'EXTERNAL_PHYSICAL_CARRIER', in_lineage: false, role: 'MATERIALISATION_ONLY' });
  }

  createSpace(parentCarrier, generation, ordinal) {
    const parentPart = parentCarrier === this.virtualRoot ? 'ROOT' : seg(parentCarrier.split('/').slice(-2).join('-'));
    const coordinate = `${this.virtualRoot}/G${generation}/${parentPart}/M${String(ordinal).padStart(4, '0')}`;
    const space = new VirtualMachineSpace({ coordinate, lineageRoot: this.virtualRoot, parentCarrier, generation, template: this.template });
    this.spaces.set(coordinate, space);
    this.ledger.append('DERIVE_VIRTUAL_MACHINE_SPACE', {
      machine_coordinate: coordinate,
      parent_virtual_carrier: parentCarrier,
      generation,
      machine_template_ref: this.template.coordinate,
      hardware_contract_complete: true
    });
    return space;
  }

  expand() {
    this.ledger.append('SEED_HARDWARE_FABRIC', { seed: this.seed, machine_template_ref: this.template.coordinate });
    let frontier = [this.createSpace(this.virtualRoot, 1, 1)];
    let ordinal = 2;
    for (let generation = 2; generation <= this.depth; generation += 1) {
      const next = [];
      for (const parent of frontier) {
        for (let i = 0; i < this.fanout; i += 1) next.push(this.createSpace(parent.coordinate, generation, ordinal++));
      }
      frontier = next;
    }
    this.ledger.append('CLOSE_HARDWARE_MONOLITH', this.metrics());
    return this.metrics();
  }

  metrics() {
    const byGeneration = {};
    for (const space of this.spaces.values()) byGeneration[space.generation] = (byGeneration[space.generation] ?? 0) + 1;
    return Object.freeze({
      virtual_root: this.virtualRoot,
      shared_machine_templates: 1,
      virtual_machine_spaces: this.spaces.size,
      max_generation: Math.max(0, ...[...this.spaces.values()].map((s) => s.generation)),
      machine_contract_families: REQUIRED_FAMILIES.length,
      all_spaces_hardware_complete: [...this.spaces.values()].every((s) => s.hardware.complete),
      host_in_lineage: false,
      by_generation: byGeneration,
      logical_machine_count_not_resident_payload_count: true
    });
  }

  eligibleTargets(sourceCoordinate, requiredFamilies = REQUIRED_FAMILIES) {
    return [...this.spaces.values()].filter((s) => {
      if (s.coordinate === sourceCoordinate) return false;
      if (!s.hardware.complete) return false;
      return requiredFamilies.every((f) => s.capabilities.has(f));
    });
  }

  selectDistinctRandom(candidates, count, label) {
    if (count < 1) throw new Error('count must be >=1');
    if (candidates.length < count) throw new Error(`Not enough candidates for ${label}: need ${count}, have ${candidates.length}`);
    const pool = [...candidates];
    const selected = [];
    for (let i = 0; i < count; i += 1) {
      const e = this.entropy.index(pool.length, `${label}:${i}`);
      const [choice] = pool.splice(e.value, 1);
      selected.push({ choice, entropy: e });
    }
    return selected;
  }

  materialiseLineage({ lineageCoordinate, sourceSpace, stateRefs, materialisationState = 'ACTIVE' }) {
    const id = `${lineageCoordinate}/MATERIALISATION/${seg(sourceSpace.coordinate)}/${this.materialisations.size + 1}`;
    const m = Object.freeze({
      materialisation_id: id,
      lineage_coordinate: lineageCoordinate,
      carrier_machine: sourceSpace.coordinate,
      state_refs: stateRefs,
      state: materialisationState,
      carrier_in_lineage: false
    });
    this.materialisations.set(id, m);
    this.ledger.append('MATERIALISE_LINEAGE', m);
    return m;
  }

  rehydrate({ materialisation, fanout = 1, mode = 'FAILOVER_REHYDRATION' }) {
    const sourceSpace = this.spaces.get(materialisation.carrier_machine);
    if (!sourceSpace) throw new Error('Source materialisation carrier is not in this fabric');
    const candidates = this.eligibleTargets(sourceSpace.coordinate);
    const picked = this.selectDistinctRandom(candidates, fanout, `REHYDRATE:${materialisation.lineage_coordinate}`);
    const receipts = [];
    for (const { choice, entropy } of picked) {
      const id = `${materialisation.lineage_coordinate}/REHYDRATED/${seg(choice.coordinate)}/${this.materialisations.size + 1}`;
      const receipt = Object.freeze({
        materialisation_id: id,
        lineage_coordinate: materialisation.lineage_coordinate,
        prior_materialisation: materialisation.materialisation_id,
        source_carrier: sourceSpace.coordinate,
        target_carrier: choice.coordinate,
        target_generation: choice.generation,
        machine_template_ref: choice.templateRef,
        hardware_contract_complete: choice.hardware.complete,
        state_refs: materialisation.state_refs,
        transition: 'REHYDRATES_TO',
        mode,
        entropy_observation: entropy,
        lineage_rewritten: false,
        physical_host_ancestor: false,
        verification_state: 'REHYDRATED_VIRTUAL_STATE_PENDING_EXTERNAL_MATERIALISATION_READBACK'
      });
      this.materialisations.set(id, receipt);
      this.ledger.append('REHYDRATE_LINEAGE', receipt);
      receipts.push(receipt);
    }
    return receipts;
  }

  simulateRandomRehydration({ events = 32, rehydrationFanout = 1 } = {}) {
    if (!this.spaces.size) this.expand();
    const spaces = [...this.spaces.values()];
    const rootWorkload = 'KEX://WORKLOAD/GLOBAL-MESH-STATE';
    const firstSourceEntropy = this.entropy.index(spaces.length, 'INITIAL_MATERIALISATION_SOURCE');
    const initialSpace = spaces[firstSourceEntropy.value];
    let active = this.materialiseLineage({ lineageCoordinate: rootWorkload, sourceSpace: initialSpace, stateRefs: initialSpace.machineState });
    const history = [];
    for (let i = 0; i < events; i += 1) {
      this.ledger.append('MATERIALISATION_LOSS_OBSERVED', { materialisation_id: active.materialisation_id, carrier_machine: active.carrier_machine ?? active.target_carrier, event_index: i + 1 });
      const normalized = active.carrier_machine ? active : Object.freeze({ ...active, carrier_machine: active.target_carrier });
      const receipts = this.rehydrate({ materialisation: normalized, fanout: rehydrationFanout, mode: rehydrationFanout > 1 ? 'FAILOVER_EXPANSION_REHYDRATION' : 'FAILOVER_REHYDRATION' });
      history.push(receipts);
      const continuationEntropy = this.entropy.index(receipts.length, `CONTINUATION:${i + 1}`);
      active = Object.freeze({ ...receipts[continuationEntropy.value], carrier_machine: receipts[continuationEntropy.value].target_carrier });
    }
    const distinctTargets = new Set(history.flat().map((r) => r.target_carrier));
    return Object.freeze({
      schema: 'kex.virtual.hardware.rehydration.fabric.v1',
      evidence_boundary: 'SOFTWARE_MODEL_ONLY_NO_PHYSICAL_HARDWARE_OR_WAN_CLAIM',
      machine_template: this.template,
      fabric_metrics: this.metrics(),
      workload_lineage: rootWorkload,
      rehydration_events: events,
      rehydration_fanout: rehydrationFanout,
      distinct_random_target_meshes: distinctTargets.size,
      latest_materialisation: active,
      entropy_tape: this.entropy.recorded,
      route_ledger: this.ledger.events,
      invariants: {
        physical_host_in_lineage: false,
        lineage_rewritten_on_rehydration: false,
        machine_contract_complete_on_all_targets: history.flat().every((r) => r.hardware_contract_complete),
        random_selection_is_over_eligible_virtual_machine_spaces: true,
        shared_machine_template_count: 1,
        virtual_machine_spaces_emulate_hardware_contract: this.spaces.size
      }
    });
  }
}

function parseArgs(argv) {
  const out = { seed: 'KEX-HARDWARE-MESH-V1', fanout: 4, depth: 4, events: 64, rehydrationFanout: 1, replay: null };
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
  for (const [k, v] of [['events', out.events], ['rehydrationFanout', out.rehydrationFanout]]) if (!Number.isInteger(v) || v < 1) throw new Error(`${k} must be positive integer`);
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  let replayEntropy = [];
  if (args.replay) {
    const body = JSON.parse(fs.readFileSync(args.replay, 'utf8'));
    replayEntropy = (body.entropy_tape ?? body).map((e) => typeof e === 'number' ? e : e.value);
  }
  const fabric = new VirtualHardwareFabric({ seed: args.seed, fanout: args.fanout, depth: args.depth, replayEntropy });
  fabric.expand();
  const result = fabric.simulateRandomRehydration({ events: args.events, rehydrationFanout: args.rehydrationFanout });
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
}

main();
