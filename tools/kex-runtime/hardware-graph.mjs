import {
  CLOSURE_ORDER,
  GLOBAL_INVARIANTS,
  HARDWARE_FAMILIES,
  HARDWARE_FAMILY_NAMES,
  MACHINE_TEMPLATE_COORDINATE,
  makeMachineStateRefs,
  normalizeSegment
} from './contracts.mjs';

export class MachineTemplate {
  constructor() {
    this.coordinate = MACHINE_TEMPLATE_COORDINATE;
    this.hardwareFamilies = HARDWARE_FAMILIES;
    this.role = 'INVARIANT_GENERATOR';
    this.resident_payload_class = 'SHARED_TEMPLATE';
  }
}

export class VirtualMachineSpace {
  constructor({ coordinate, lineageRoot, parentCarrier, generation, template }) {
    this.coordinate = coordinate;
    this.lineageRoot = lineageRoot;
    this.parentCarrier = parentCarrier;
    this.generation = generation;
    this.templateRef = template.coordinate;
    this.resolvedFamilies = new Set();
    this.stateRefs = makeMachineStateRefs(coordinate);
    this.state = 'VIRTUAL_ADDRESSABLE';
    this.capabilityClass = 'HARDWARE_DERIVABLE';
  }

  resolveFamily(family) {
    if (!HARDWARE_FAMILIES[family]) throw new Error(`Unknown hardware family ${family}`);
    const before = this.resolvedFamilies.size;
    this.resolvedFamilies.add(family);
    if (this.resolvedFamilies.size === HARDWARE_FAMILY_NAMES.length) {
      this.state = 'CARRIER_READY';
      this.capabilityClass = 'HARDWARE_COMPLETE';
    }
    return this.resolvedFamilies.size !== before;
  }

  get hardwareComplete() {
    return this.resolvedFamilies.size === HARDWARE_FAMILY_NAMES.length;
  }

  descriptor() {
    return Object.freeze({
      coordinate: this.coordinate,
      lineage_root: this.lineageRoot,
      parent_virtual_carrier: this.parentCarrier,
      generation: this.generation,
      machine_template_ref: this.templateRef,
      resolved_hardware_families: Object.freeze([...this.resolvedFamilies]),
      hardware_family_count: this.resolvedFamilies.size,
      required_hardware_family_count: HARDWARE_FAMILY_NAMES.length,
      hardware_complete: this.hardwareComplete,
      state: this.state,
      capability_class: this.capabilityClass,
      state_refs: this.stateRefs,
      physical_performance_equivalence_claim: false
    });
  }
}

export class VirtualHardwareGraph {
  constructor({ seed, fanout, depth, ledger }) {
    if (!Number.isInteger(fanout) || fanout < 1 || fanout > 32) throw new Error('fanout must be 1..32');
    if (!Number.isInteger(depth) || depth < 1 || depth > 8) throw new Error('depth must be 1..8');
    this.seed = normalizeSegment(seed);
    this.root = `KEX://HARDWARE-MESH/${this.seed}`;
    this.template = new MachineTemplate();
    this.fanout = fanout;
    this.depth = depth;
    this.ledger = ledger;
    this.spaces = new Map();
    this.ordinal = 1;
  }

  createSpace(parentCarrier, generation) {
    const coordinate = `${this.root}/G${generation}/M${String(this.ordinal++).padStart(6, '0')}`;
    const space = new VirtualMachineSpace({
      coordinate,
      lineageRoot: this.root,
      parentCarrier,
      generation,
      template: this.template
    });
    this.spaces.set(coordinate, space);
    this.ledger.append('DERIVE_MACHINE_DESCRIPTOR', {
      machine_coordinate: coordinate,
      parent_virtual_carrier: parentCarrier,
      generation,
      template_ref: this.template.coordinate,
      physical_host_ancestor: false
    });
    return space;
  }

  closeMachineContract(space) {
    for (const family of CLOSURE_ORDER) {
      if (space.resolveFamily(family)) {
        this.ledger.append('RESOLVE_HARDWARE_FAMILY', {
          machine_coordinate: space.coordinate,
          family,
          components: HARDWARE_FAMILIES[family],
          resolved_count: space.resolvedFamilies.size
        });
      }
    }
    if (!space.hardwareComplete) throw new Error(`${space.coordinate}: hardware closure incomplete`);
    this.ledger.append('CLOSE_MACHINE_CONTRACT', {
      machine_coordinate: space.coordinate,
      generation: space.generation,
      carrier_ready: true,
      physical_host_ancestor: false
    });
    return space;
  }

  expandAndClose() {
    this.ledger.append('SEED_HARDWARE_GRAPH', {
      seed: this.seed,
      template_ref: this.template.coordinate,
      invariants: GLOBAL_INVARIANTS
    });

    const rootCarrier = this.closeMachineContract(this.createSpace(this.root, 1));
    let frontier = [rootCarrier];
    for (let generation = 2; generation <= this.depth; generation += 1) {
      const next = [];
      for (const parent of frontier) {
        if (!parent.hardwareComplete || parent.state !== 'CARRIER_READY') {
          throw new Error(`${parent.coordinate}: cannot derive child before parent carrier closure`);
        }
        for (let i = 0; i < this.fanout; i += 1) {
          const child = this.createSpace(parent.coordinate, generation);
          this.ledger.append('PARENT_CARRIER_ADMITS_CHILD', {
            parent_virtual_carrier: parent.coordinate,
            child_machine_coordinate: child.coordinate,
            parent_carrier_ready: true
          });
          next.push(this.closeMachineContract(child));
        }
      }
      frontier = next;
    }
    this.ledger.append('CLOSE_HARDWARE_GRAPH', this.metrics());
    return this.metrics();
  }

  eligibleCarriers({ exclude = new Set(), requiredFamilies = HARDWARE_FAMILY_NAMES } = {}) {
    return [...this.spaces.values()].filter((space) =>
      !exclude.has(space.coordinate) &&
      space.hardwareComplete &&
      requiredFamilies.every((family) => space.resolvedFamilies.has(family))
    );
  }

  metrics() {
    const values = [...this.spaces.values()];
    const byGeneration = {};
    for (const s of values) byGeneration[s.generation] = (byGeneration[s.generation] ?? 0) + 1;
    const complete = values.filter((s) => s.hardwareComplete).length;
    return Object.freeze({
      virtual_root: this.root,
      shared_machine_templates: 1,
      virtual_machine_descriptors: values.length,
      hardware_complete_carriers: complete,
      incomplete_descriptors: values.length - complete,
      max_generation: values.reduce((m, s) => Math.max(m, s.generation), 0),
      hardware_family_count: HARDWARE_FAMILY_NAMES.length,
      host_in_lineage: false,
      resident_machine_payloads_created: 0,
      by_generation: Object.freeze(byGeneration)
    });
  }
}
