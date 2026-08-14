import { normalizeSegment } from './contracts.mjs';

const SERVICE_GRAMMAR = Object.freeze({
  IDENTITY: Object.freeze({ roles: ['AUTHORITY', 'MEMBERSHIP', 'CREDENTIAL', 'TRUST'], accepts: ['identity.request', 'proof.receipt', 'membership.state'], emits: ['identity.proof', 'authority.token', 'membership.state'] }),
  STATE: Object.freeze({ roles: ['SNAPSHOT', 'DELTA', 'MIRROR', 'COMMIT'], accepts: ['state.request', 'proof.receipt', 'recovery.ready'], emits: ['state.frame', 'state.delta', 'recovery.state'] }),
  COMPUTE: Object.freeze({ roles: ['SCHEDULER', 'WORKER', 'RESULT', 'DISPATCH'], accepts: ['compute.request', 'state.frame', 'authority.token'], emits: ['compute.result', 'compute.plan', 'proof.verify'] }),
  STORAGE: Object.freeze({ roles: ['READ', 'WRITE', 'SNAPSHOT', 'REHYDRATE'], accepts: ['storage.read', 'storage.write', 'state.frame'], emits: ['storage.object', 'recovery.state', 'proof.path', 'source.object'] }),
  NETWORK: Object.freeze({ roles: ['DISCOVERY', 'ROUTE', 'BRIDGE', 'PEER'], accepts: ['network.resolve', 'domain.route', 'authority.token'], emits: ['network.route', 'transport.edge', 'identity.request'] }),
  PROOF: Object.freeze({ roles: ['PATH', 'VERIFY', 'RECEIPT', 'ANCHOR'], accepts: ['proof.verify', 'proof.path', 'compute.result', 'storage.object'], emits: ['proof.receipt', 'state.delta', 'identity.request'] }),
  RECOVERY: Object.freeze({ roles: ['SELECT', 'RESTORE', 'VERIFY', 'PROMOTE'], accepts: ['recovery.request', 'recovery.state', 'proof.receipt'], emits: ['recovery.ready', 'state.frame', 'storage.read'] }),
  SITE: Object.freeze({ roles: ['BUILD', 'PROJECTION', 'DOMAIN', 'RECOVERY'], accepts: ['site.intent', 'source.object', 'domain.route', 'state.frame'], emits: ['site.state', 'storage.read', 'network.resolve', 'proof.verify'] }),
  AGENT: Object.freeze({ roles: ['PLAN', 'EXECUTE', 'OBSERVE', 'HANDOFF'], accepts: ['agent.intent', 'compute.result', 'state.frame'], emits: ['compute.request', 'proof.verify', 'resolve.intent'] }),
  RESOLVER: Object.freeze({ roles: ['MATCH', 'COMPOSE', 'ROUTE', 'CLOSE'], accepts: ['resolve.intent', 'network.route', 'state.frame'], emits: ['resolve.result', 'network.resolve', 'compute.request'] })
});

const FAMILIES = Object.freeze(Object.keys(SERVICE_GRAMMAR));

export class VirtualServiceGraph {
  constructor({ seed, depth = 3, ledger }) {
    if (!Number.isInteger(depth) || depth < 1 || depth > 16) throw new Error('service depth must be 1..16');
    this.seed = normalizeSegment(seed);
    this.root = `KEX://SERVICE-MESH/${this.seed}`;
    this.depth = depth;
    this.ledger = ledger;
    this.services = new Map();
    this.edges = new Map();
  }

  makeService({ family, role, depth, parent }) {
    const coordinate = `${parent}/${family}/${normalizeSegment(role)}/D${depth}`;
    const spec = SERVICE_GRAMMAR[family];
    return Object.freeze({
      coordinate,
      family,
      role,
      depth,
      parent_id: parent,
      lineage_root: this.root,
      accepts: Object.freeze([...new Set(spec.accepts)].sort()),
      emits: Object.freeze([...new Set(spec.emits)].sort()),
      state: 'VIRTUAL_ADDRESSABLE'
    });
  }

  addEdge(source, target, relation, token = null) {
    if (source === target) return false;
    const key = `${source}|${relation}|${token ?? ''}|${target}`;
    if (this.edges.has(key)) return false;
    const edge = Object.freeze({ source, target, relation, token });
    this.edges.set(key, edge);
    this.ledger.append('SERVICE_EDGE', edge);
    return true;
  }

  ignite() {
    this.ledger.append('SEED_SERVICE_GRAPH', { service_root: this.root, families: FAMILIES });
    let frontier = [];
    for (const family of FAMILIES) {
      const service = this.makeService({ family, role: 'ROOT', depth: 1, parent: this.root });
      this.services.set(service.coordinate, service);
      this.addEdge(this.root, service.coordinate, 'DERIVES');
      this.ledger.append('DERIVE_SERVICE', { service_coordinate: service.coordinate, family, depth: 1 });
      frontier.push(service);
    }

    for (let depth = 2; depth <= this.depth; depth += 1) {
      const next = [];
      for (const parent of frontier) {
        const spec = SERVICE_GRAMMAR[parent.family];
        const roleAtom = spec.roles[(depth - 2) % spec.roles.length];
        const service = this.makeService({ family: parent.family, role: `${parent.role}.${roleAtom}`, depth, parent: parent.coordinate });
        this.services.set(service.coordinate, service);
        this.addEdge(parent.coordinate, service.coordinate, 'DERIVES');
        this.ledger.append('DERIVE_SERVICE', { service_coordinate: service.coordinate, parent_id: parent.coordinate, family: service.family, depth });
        next.push(service);
      }
      frontier = next;
    }

    this.closeCompatibleRelations();
    const metrics = this.metrics();
    this.ledger.append('CLOSE_SERVICE_GRAPH', metrics);
    return metrics;
  }

  closeCompatibleRelations() {
    const list = [...this.services.values()];
    for (const source of list) {
      for (const target of list) {
        if (source.coordinate === target.coordinate) continue;
        const shared = source.emits.filter((token) => target.accepts.includes(token));
        if (!shared.length) continue;
        const relation = source.parent_id === target.parent_id ? 'SISTER_LINK' : 'COUSIN_LINK';
        for (const token of shared) this.addEdge(source.coordinate, target.coordinate, relation, token);
      }
    }
  }

  connectedCount() {
    const nodes = [...this.services.keys()];
    if (!nodes.length) return 0;
    const adj = new Map(nodes.map((n) => [n, new Set()]));
    for (const edge of this.edges.values()) {
      if (!adj.has(edge.source) || !adj.has(edge.target)) continue;
      adj.get(edge.source).add(edge.target);
      adj.get(edge.target).add(edge.source);
    }
    const seen = new Set([nodes[0]]);
    const queue = [nodes[0]];
    while (queue.length) {
      const current = queue.shift();
      for (const next of adj.get(current) ?? []) {
        if (!seen.has(next)) {
          seen.add(next);
          queue.push(next);
        }
      }
    }
    return seen.size;
  }

  metrics() {
    const services = [...this.services.values()];
    const edges = [...this.edges.values()];
    const connected = this.connectedCount();
    const cousinEdges = edges.filter((e) => e.relation === 'COUSIN_LINK');
    const crossPairs = new Set();
    for (const edge of cousinEdges) {
      const a = this.services.get(edge.source);
      const b = this.services.get(edge.target);
      if (a && b && a.family !== b.family) crossPairs.add([a.family, b.family].sort().join('<->'));
    }
    return Object.freeze({
      service_root: this.root,
      families: new Set(services.map((s) => s.family)).size,
      virtual_services: services.length,
      max_depth: services.reduce((m, s) => Math.max(m, s.depth), 0),
      derivation_edges: edges.filter((e) => e.relation === 'DERIVES').length,
      sister_links: edges.filter((e) => e.relation === 'SISTER_LINK').length,
      cousin_links: cousinEdges.length,
      cross_family_pairs: crossPairs.size,
      connected_services: connected,
      connected_ratio: services.length ? connected / services.length : 0,
      host_in_lineage: false
    });
  }
}
