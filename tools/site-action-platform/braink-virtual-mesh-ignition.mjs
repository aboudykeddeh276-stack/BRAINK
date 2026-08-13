#!/usr/bin/env node

const FAMILY_INTERFACE = {
  IDENTITY: { roles: ['AUTHORITY','MEMBERSHIP','CREDENTIAL','TRUST'], accepts: ['identity.request','proof.receipt','membership.state'], emits: ['identity.proof','authority.token','membership.state'] },
  STATE: { roles: ['SNAPSHOT','DELTA','MIRROR','COMMIT'], accepts: ['state.request','proof.receipt','recovery.ready'], emits: ['state.frame','state.delta','recovery.state'] },
  COMPUTE: { roles: ['SCHEDULER','WORKER','RESULT','DISPATCH'], accepts: ['compute.request','state.frame','authority.token'], emits: ['compute.result','compute.plan','proof.verify'] },
  STORAGE: { roles: ['READ','WRITE','SNAPSHOT','REHYDRATE'], accepts: ['storage.read','storage.write','state.frame'], emits: ['storage.object','recovery.state','proof.path','source.object'] },
  NETWORK: { roles: ['DISCOVERY','ROUTE','BRIDGE','PEER'], accepts: ['network.resolve','domain.route','authority.token'], emits: ['network.route','transport.edge','identity.request'] },
  PROOF: { roles: ['PATH','VERIFY','RECEIPT','ANCHOR'], accepts: ['proof.verify','proof.path','compute.result','storage.object'], emits: ['proof.receipt','state.delta','identity.request'] },
  RECOVERY: { roles: ['SELECT','RESTORE','VERIFY','PROMOTE'], accepts: ['recovery.request','recovery.state','proof.receipt'], emits: ['recovery.ready','state.frame','storage.read'] },
  SITE: { roles: ['BUILD','PROJECTION','DOMAIN','RECOVERY'], accepts: ['site.intent','source.object','domain.route','state.frame'], emits: ['site.state','storage.read','network.resolve','proof.verify'] },
  AGENT: { roles: ['PLAN','EXECUTE','OBSERVE','HANDOFF'], accepts: ['agent.intent','compute.result','state.frame'], emits: ['compute.request','proof.verify','resolve.intent'] },
  RESOLVER: { roles: ['MATCH','COMPOSE','ROUTE','CLOSE'], accepts: ['resolve.intent','network.route','state.frame'], emits: ['resolve.result','network.resolve','compute.request'] }
};

const ROOT_FAMILIES = Object.keys(FAMILY_INTERFACE);

function encodeSegment(value) {
  return String(value).trim().replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'STATE';
}

function parseArgs(argv) {
  const out = { maxDepth: 8, seed: 'KEX-BRAINK-MESH-V2', selfTest: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--max-depth') out.maxDepth = Number(argv[++i]);
    else if (arg === '--seed') out.seed = argv[++i];
    else if (arg === '--self-test') out.selfTest = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!Number.isInteger(out.maxDepth) || out.maxDepth < 1 || out.maxDepth > 64) {
    throw new Error('--max-depth must be an integer from 1..64');
  }
  return out;
}

function kexCompose(left, right) {
  return Object.freeze({ operator: 'HEXxHEX_CLASS_COMPOSITION', left, right, result: `KEX<${left}×${right}>` });
}

function makeService({ family, role, depth, parentId, lineageRoot }) {
  const coordinate = `${parentId}/${encodeSegment(family)}/${encodeSegment(role)}/D${depth}`;
  const spec = FAMILY_INTERFACE[family];
  return Object.freeze({
    id: coordinate,
    coordinate,
    family,
    role,
    depth,
    parent_id: parentId,
    lineage_root: lineageRoot,
    composition: kexCompose(parentId, `${family}:${role}:D${depth}`),
    accepts: [...new Set(spec.accepts)].sort(),
    emits: [...new Set(spec.emits)].sort(),
    state: 'VIRTUAL_ADDRESSABLE'
  });
}

class VirtualMesh {
  constructor(seed, maxDepth) {
    this.seed = seed;
    this.maxDepth = maxDepth;
    this.hostEnvelope = Object.freeze({
      boundary: 'EXTERNAL_EXECUTION_ENVELOPE',
      in_lineage: false,
      proof_authority: false,
      purpose: 'ignite heartbeat and expose KEX virtual root only'
    });
    this.virtualRoot = `KEX://ROOT/${encodeSegment(seed)}`;
    this.services = new Map();
    this.edges = new Map();
    this.derivationKeys = new Set();
    this.transitionLedger = [];
    this.heartbeat = 0;
    this.leap = null;
  }

  record(event, payload = {}) {
    const entry = Object.freeze({
      seq: this.transitionLedger.length + 1,
      event,
      heartbeat: this.heartbeat,
      observer: 'KEX://OBSERVER/1',
      lineage_root: this.virtualRoot,
      ...payload
    });
    this.transitionLedger.push(entry);
    return entry;
  }

  pulse() {
    this.heartbeat += 1;
    this.record('HEARTBEAT', { state: 'ACTIVE' });
    return this.heartbeat;
  }

  addEdge(source, target, relation, proof = {}) {
    if (source === target) return false;
    const key = `${source}|${relation}|${proof.token ?? ''}|${target}`;
    if (this.edges.has(key)) return false;
    const edge = Object.freeze({ source, target, relation, ...proof });
    this.edges.set(key, edge);
    this.record('TRAVERSE_EDGE', edge);
    return true;
  }

  seedRoots() {
    this.record('SEED', { seed: this.seed, virtual_root: this.virtualRoot });
    for (const family of ROOT_FAMILIES) {
      const service = makeService({ family, role: 'ROOT', depth: 1, parentId: this.virtualRoot, lineageRoot: this.virtualRoot });
      this.services.set(service.id, service);
      this.addEdge(this.virtualRoot, service.id, 'DERIVES', { phase: 'EXPAND' });
      this.record('EXPAND_SERVICE', { service_id: service.id, family, depth: 1 });
    }
  }

  deriveFrom(service) {
    if (service.depth >= this.maxDepth) return 0;
    const spec = FAMILY_INTERFACE[service.family];
    const roleAtom = spec.roles[(service.depth - 1) % spec.roles.length];
    const role = `${service.role}.${roleAtom}`;
    const derivationKey = `${service.id}|${role}|D${service.depth + 1}`;
    if (this.derivationKeys.has(derivationKey)) return 0;
    this.derivationKeys.add(derivationKey);
    const child = makeService({ family: service.family, role, depth: service.depth + 1, parentId: service.id, lineageRoot: service.lineage_root });
    if (this.services.has(child.id)) return 0;
    this.services.set(child.id, child);
    this.addEdge(service.id, child.id, 'DERIVES', { phase: 'EXPAND' });
    this.record('EXPAND_SERVICE', { service_id: child.id, parent_id: service.id, family: child.family, depth: child.depth });
    return 1;
  }

  deriveFrontier() {
    const snapshot = [...this.services.values()];
    let created = 0;
    for (const service of snapshot) created += this.deriveFrom(service);
    return created;
  }

  linkCompatible() {
    const list = [...this.services.values()];
    let added = 0;
    for (let i = 0; i < list.length; i += 1) {
      const a = list[i];
      for (let j = 0; j < list.length; j += 1) {
        if (i === j) continue;
        const b = list[j];
        const shared = a.emits.filter((token) => b.accepts.includes(token));
        if (shared.length === 0) continue;
        const relation = a.parent_id === b.parent_id ? 'SISTER_LINK' : 'COUSIN_LINK';
        for (const token of shared) {
          if (this.addEdge(a.id, b.id, relation, { token, phase: 'TRAVERSE' })) added += 1;
        }
      }
    }
    return added;
  }

  connectedServiceIds() {
    const adj = new Map();
    const add = (a, b) => {
      if (!adj.has(a)) adj.set(a, new Set());
      adj.get(a).add(b);
    };
    for (const edge of this.edges.values()) {
      if (edge.source === this.virtualRoot || edge.target === this.virtualRoot) continue;
      add(edge.source, edge.target);
      add(edge.target, edge.source);
    }
    const first = this.services.keys().next().value;
    if (!first) return new Set();
    const seen = new Set([first]);
    const queue = [first];
    while (queue.length) {
      const current = queue.shift();
      for (const next of adj.get(current) ?? []) {
        if (!seen.has(next)) { seen.add(next); queue.push(next); }
      }
    }
    return seen;
  }

  metrics() {
    const values = [...this.services.values()];
    const edges = [...this.edges.values()];
    const lateral = edges.filter((e) => e.relation === 'SISTER_LINK' || e.relation === 'COUSIN_LINK');
    const cousin = lateral.filter((e) => e.relation === 'COUSIN_LINK');
    const families = new Set(values.map((s) => s.family));
    const maxDepth = values.reduce((m, s) => Math.max(m, s.depth), 0);
    const crossFamilyPairs = new Set();
    for (const edge of cousin) {
      const a = this.services.get(edge.source);
      const b = this.services.get(edge.target);
      if (!a || !b || a.family === b.family) continue;
      crossFamilyPairs.add([a.family, b.family].sort().join('<->'));
    }
    const connected = this.connectedServiceIds();
    return {
      heartbeat: this.heartbeat,
      virtual_root: this.virtualRoot,
      services: values.length,
      families: families.size,
      max_virtual_depth: maxDepth,
      derivation_edges: edges.filter((e) => e.relation === 'DERIVES').length,
      sister_links: lateral.filter((e) => e.relation === 'SISTER_LINK').length,
      cousin_links: cousin.length,
      cross_family_pairs: crossFamilyPairs.size,
      connected_services: connected.size,
      connected_ratio: values.length ? connected.size / values.length : 0,
      host_in_lineage: false
    };
  }

  leapGate() {
    const m = this.metrics();
    const pass = m.families >= 10 && m.max_virtual_depth >= Math.min(3, this.maxDepth) && m.cousin_links >= 10 && m.cross_family_pairs >= 6 && m.connected_ratio >= 0.8 && m.host_in_lineage === false;
    return { pass, metrics: m };
  }

  kexProofRoute() {
    const gate = this.leapGate();
    const path = this.transitionLedger.map((e) => ({
      seq: e.seq, event: e.event, heartbeat: e.heartbeat,
      service_id: e.service_id ?? null, source: e.source ?? null, target: e.target ?? null,
      relation: e.relation ?? null, token: e.token ?? null
    }));
    return Object.freeze({
      schema: 'kex.proof.route.v1',
      authority_model: 'IDENTITY_INPUT_PATH_RULE_OBSERVER_COMMIT_ORDER',
      seed: this.seed,
      virtual_root: this.virtualRoot,
      observer: 'KEX://OBSERVER/1',
      rule: 'HEX × HEX = KEX; STATE is primitive; traversal is evidence',
      phases: ['SEED','EXPAND','TRAVERSE','COLLAPSE','REHYDRATE'],
      commit_order: path,
      collapse: gate,
      endpoint_digest_is_authority: false
    });
  }

  virtualMonolith() {
    const gate = this.leapGate();
    if (!gate.pass) return null;
    this.record('COLLAPSE', { state: 'GRAPH_CLOSURE', metrics: gate.metrics });
    return Object.freeze({
      schema: 'braink.virtual.monolith.v2',
      location: 'VIRTUAL_ONLY',
      host_materialisation: 'BOOTSTRAP_HEARTBEAT_RECEIPT_ONLY',
      lineage_root: this.virtualRoot,
      kex_coordinate: `KEX://MONOLITH/${encodeSegment(this.seed)}/D${gate.metrics.max_virtual_depth}/S${gate.metrics.services}/E${this.edges.size}`,
      service_count: gate.metrics.services,
      edge_count: this.edges.size,
      virtual_depth: gate.metrics.max_virtual_depth,
      proof_model: 'KEX_ROUTE_LINEAGE',
      state: 'LEAP_ACHIEVED'
    });
  }

  igniteUntilLeap() {
    this.seedRoots();
    for (let cycle = 1; cycle <= this.maxDepth + 2; cycle += 1) {
      this.pulse();
      const derived = this.deriveFrontier();
      const linked = this.linkCompatible();
      const gate = this.leapGate();
      if (gate.pass) {
        this.leap = this.virtualMonolith();
        return { cycle, derived, linked, gate, monolith: this.leap, proof: this.kexProofRoute() };
      }
      if (derived === 0 && linked === 0) break;
    }
    return { cycle: this.heartbeat, gate: this.leapGate(), monolith: null, proof: this.kexProofRoute() };
  }
}

function rehydrate(seed, maxDepth, original) {
  const replay = new VirtualMesh(seed, maxDepth).igniteUntilLeap();
  const originalServices = [...original.proof.commit_order].filter((e) => e.event === 'EXPAND_SERVICE').map((e) => e.service_id);
  const replayServices = [...replay.proof.commit_order].filter((e) => e.event === 'EXPAND_SERVICE').map((e) => e.service_id);
  const routeEqual = JSON.stringify(originalServices) === JSON.stringify(replayServices);
  const metricsEqual = JSON.stringify(original.gate.metrics) === JSON.stringify(replay.gate.metrics);
  return {
    state: routeEqual && metricsEqual ? 'REHYDRATED_EQUIVALENT' : 'REHYDRATION_DIVERGED',
    route_equal: routeEqual,
    metrics_equal: metricsEqual,
    replay_virtual_root: replay.gate.metrics.virtual_root
  };
}

function execute(seed, maxDepth) {
  const mesh = new VirtualMesh(seed, maxDepth);
  const result = mesh.igniteUntilLeap();
  const rehydration = rehydrate(seed, maxDepth, result);
  mesh.record('REHYDRATE', rehydration);
  return { ...result, proof: mesh.kexProofRoute(), rehydration };
}

function selfTest() {
  const result = execute('KEX-BRAINK-MESH-V2-SELF-TEST', 8);
  if (!result.gate.pass) throw new Error(`LEAP gate failed: ${JSON.stringify(result.gate.metrics)}`);
  if (result.gate.metrics.host_in_lineage !== false) throw new Error('Host leaked into lineage');
  if (!result.monolith || result.monolith.location !== 'VIRTUAL_ONLY') throw new Error('Monolith is not virtual-only');
  if (result.monolith.proof_model !== 'KEX_ROUTE_LINEAGE') throw new Error('Wrong proof model');
  if (result.rehydration.state !== 'REHYDRATED_EQUIVALENT') throw new Error('Rehydration failed');
  return { pass: true, result };
}

const args = parseArgs(process.argv.slice(2));
const output = args.selfTest ? selfTest() : execute(args.seed, args.maxDepth);
process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
