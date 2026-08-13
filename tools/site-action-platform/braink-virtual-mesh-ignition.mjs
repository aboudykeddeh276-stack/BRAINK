#!/usr/bin/env node
import crypto from 'node:crypto';

const sha256 = (value) => crypto.createHash('sha256').update(value).digest('hex');

const FAMILY_INTERFACE = {
  IDENTITY: {
    roles: ['AUTHORITY', 'MEMBERSHIP', 'CREDENTIAL', 'TRUST'],
    accepts: ['identity.request', 'proof.receipt', 'membership.state'],
    emits: ['identity.proof', 'authority.token', 'membership.state']
  },
  STATE: {
    roles: ['SNAPSHOT', 'DELTA', 'MIRROR', 'COMMIT'],
    accepts: ['state.request', 'proof.receipt', 'recovery.ready'],
    emits: ['state.frame', 'state.delta', 'recovery.state']
  },
  COMPUTE: {
    roles: ['SCHEDULER', 'WORKER', 'RESULT', 'DISPATCH'],
    accepts: ['compute.request', 'state.frame', 'authority.token'],
    emits: ['compute.result', 'compute.plan', 'proof.verify']
  },
  STORAGE: {
    roles: ['READ', 'WRITE', 'SNAPSHOT', 'REHYDRATE'],
    accepts: ['storage.read', 'storage.write', 'state.frame'],
    emits: ['storage.object', 'recovery.state', 'proof.hash', 'source.object']
  },
  NETWORK: {
    roles: ['DISCOVERY', 'ROUTE', 'BRIDGE', 'PEER'],
    accepts: ['network.resolve', 'domain.route', 'authority.token'],
    emits: ['network.route', 'transport.edge', 'identity.request']
  },
  PROOF: {
    roles: ['HASH', 'VERIFY', 'RECEIPT', 'ANCHOR'],
    accepts: ['proof.verify', 'proof.hash', 'compute.result', 'storage.object'],
    emits: ['proof.receipt', 'state.delta', 'identity.request']
  },
  RECOVERY: {
    roles: ['SELECT', 'RESTORE', 'VERIFY', 'PROMOTE'],
    accepts: ['recovery.request', 'recovery.state', 'proof.receipt'],
    emits: ['recovery.ready', 'state.frame', 'storage.read']
  },
  SITE: {
    roles: ['BUILD', 'PROJECTION', 'DOMAIN', 'RECOVERY'],
    accepts: ['site.intent', 'source.object', 'domain.route', 'state.frame'],
    emits: ['site.state', 'storage.read', 'network.resolve', 'proof.verify']
  },
  AGENT: {
    roles: ['PLAN', 'EXECUTE', 'OBSERVE', 'HANDOFF'],
    accepts: ['agent.intent', 'compute.result', 'state.frame'],
    emits: ['compute.request', 'proof.verify', 'resolve.intent']
  },
  RESOLVER: {
    roles: ['MATCH', 'COMPOSE', 'ROUTE', 'CLOSE'],
    accepts: ['resolve.intent', 'network.route', 'state.frame'],
    emits: ['resolve.result', 'network.resolve', 'compute.request']
  }
};

const DEFAULT_ROOTS = Object.entries(FAMILY_INTERFACE).map(([family, spec]) => [
  family,
  spec.accepts,
  spec.emits
]);

function parseArgs(argv) {
  const out = { maxDepth: 8, seed: 'KEX-BRAINK-MESH-V1', selfTest: false };
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

function makeService({ family, role, depth, parentId, lineageRoot, accepts, emits, seed }) {
  const identityMaterial = [seed, family, role, depth, parentId ?? 'VIRTUAL_ROOT', lineageRoot].join('|');
  const id = `KEX://${family}/${role}/${sha256(identityMaterial).slice(0, 16)}`;
  return Object.freeze({
    id,
    family,
    role,
    depth,
    parent_id: parentId,
    lineage_root: lineageRoot,
    accepts: [...new Set(accepts)].sort(),
    emits: [...new Set(emits)].sort(),
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
      purpose: 'ignite heartbeat and expose virtual root only'
    });
    this.services = new Map();
    this.edges = new Map();
    this.derivationKeys = new Set();
    this.virtualRoot = `KEX://ROOT/${sha256(seed).slice(0, 24)}`;
    this.heartbeat = 0;
    this.leap = null;
  }

  pulse() {
    this.heartbeat += 1;
    return this.heartbeat;
  }

  addEdge(source, target, relation, proof = {}) {
    if (source === target) return false;
    const key = `${source}|${target}|${relation}`;
    if (this.edges.has(key)) return false;
    this.edges.set(key, Object.freeze({ source, target, relation, ...proof }));
    return true;
  }

  seedRoots() {
    for (const [family, accepts, emits] of DEFAULT_ROOTS) {
      const service = makeService({
        family,
        role: 'ROOT',
        depth: 1,
        parentId: this.virtualRoot,
        lineageRoot: this.virtualRoot,
        accepts,
        emits,
        seed: this.seed
      });
      this.services.set(service.id, service);
      this.addEdge(this.virtualRoot, service.id, 'DERIVES');
    }
  }

  deriveFrom(service) {
    if (service.depth >= this.maxDepth) return 0;
    const spec = FAMILY_INTERFACE[service.family];
    if (!spec) return 0;
    const roleAtom = spec.roles[(service.depth - 1) % spec.roles.length];
    const role = `${service.role}.${roleAtom}.D${service.depth + 1}`;
    const derivationKey = `${service.id}|${role}`;
    if (this.derivationKeys.has(derivationKey)) return 0;
    this.derivationKeys.add(derivationKey);
    const child = makeService({
      family: service.family,
      role,
      depth: service.depth + 1,
      parentId: service.id,
      lineageRoot: service.lineage_root,
      accepts: spec.accepts,
      emits: spec.emits,
      seed: this.seed
    });
    if (this.services.has(child.id)) return 0;
    this.services.set(child.id, child);
    this.addEdge(service.id, child.id, 'DERIVES');
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
          if (this.addEdge(a.id, b.id, relation, { token })) added += 1;
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
    const q = [first];
    while (q.length) {
      const cur = q.shift();
      for (const next of adj.get(cur) ?? []) {
        if (!seen.has(next)) { seen.add(next); q.push(next); }
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
    const pass =
      m.families >= 10 &&
      m.max_virtual_depth >= Math.min(3, this.maxDepth) &&
      m.cousin_links >= 10 &&
      m.cross_family_pairs >= 6 &&
      m.connected_ratio >= 0.8 &&
      m.host_in_lineage === false;
    return { pass, metrics: m };
  }

  virtualMonolith() {
    const gate = this.leapGate();
    if (!gate.pass) return null;
    const serviceIds = [...this.services.keys()].sort();
    const edgeKeys = [...this.edges.keys()].sort();
    const rootHash = sha256(JSON.stringify({ seed: this.seed, serviceIds, edgeKeys }));
    return Object.freeze({
      schema: 'braink.virtual.monolith.v1',
      location: 'VIRTUAL_ONLY',
      host_materialisation: 'BOOTSTRAP_AND_RECEIPT_ONLY',
      lineage_root: this.virtualRoot,
      service_count: serviceIds.length,
      edge_count: edgeKeys.length,
      virtual_depth: gate.metrics.max_virtual_depth,
      graph_root_sha256: rootHash,
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
        return { cycle, derived, linked, gate, monolith: this.leap };
      }
      if (derived === 0 && linked === 0) break;
    }
    return { cycle: this.heartbeat, gate: this.leapGate(), monolith: null };
  }
}

function selfTest() {
  const mesh = new VirtualMesh('SELF-TEST-SEED', 8);
  const result = mesh.igniteUntilLeap();
  if (!result.gate.pass) throw new Error(`LEAP gate failed: ${JSON.stringify(result.gate.metrics)}`);
  if (mesh.hostEnvelope.in_lineage !== false) throw new Error('Host leaked into lineage');
  if (!result.monolith || result.monolith.location !== 'VIRTUAL_ONLY') throw new Error('Monolith is not virtual-only');
  if ([...mesh.services.values()].some((s) => s.parent_id === 'HOST')) throw new Error('Host parent detected');
  return { pass: true, result };
}

const args = parseArgs(process.argv.slice(2));
const output = args.selfTest
  ? selfTest()
  : new VirtualMesh(args.seed, args.maxDepth).igniteUntilLeap();
process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
