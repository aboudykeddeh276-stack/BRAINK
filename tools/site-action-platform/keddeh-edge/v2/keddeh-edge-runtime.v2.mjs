#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_SEED = path.join(HERE, 'keddeh-edge.seed.v2.json');
const sha256 = (value) => crypto.createHash('sha256').update(String(value)).digest('hex');

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }
  return value;
}
const canonicalJson = (value) => JSON.stringify(stable(value));
const clone = (value) => JSON.parse(JSON.stringify(value));
function assert(condition, message) { if (!condition) throw new Error(message); }

function normalizeHost(raw) {
  const value = String(raw ?? '').trim().toLowerCase();
  if (!value) throw new Error('HOST_REQUIRED');
  const host = value.replace(/\.$/, '').replace(/:\d+$/, '');
  if (!/^[a-z0-9.-]+$/.test(host) || host.includes('..')) throw new Error('HOST_INVALID');
  return host;
}
function normalizePath(raw) {
  const pathname = new URL(String(raw ?? '/'), 'http://edge.invalid').pathname;
  const collapsed = pathname.replace(/\/{2,}/g, '/');
  return collapsed.startsWith('/') ? collapsed : `/${collapsed}`;
}
function normalizeMethod(raw) {
  const method = String(raw ?? 'GET').trim().toUpperCase();
  if (!/^[A-Z]+$/.test(method)) throw new Error('METHOD_INVALID');
  return method;
}
function normalizeCoordinate(raw, field) {
  const value = String(raw ?? '').trim();
  if (!value) throw new Error(`${field}_REQUIRED`);
  return value;
}
const interfaceHasToken = (iface, direction, token) => Array.isArray(iface?.[direction]) && iface[direction].includes(token);

export function loadSeed(seedPath = DEFAULT_SEED) {
  const text = fs.readFileSync(seedPath, 'utf8');
  const seed = JSON.parse(text);
  assert(seed.schema === 'kex.braink.keddeh-edge.seed.v2', `Unsupported seed schema: ${seed.schema}`);
  const rules = seed.governing_rules ?? {};
  for (const invariant of [
    'discover_before_derive',
    'derived_children_reenter_active_state',
    'recompute_affected_relations_after_admission',
    'observation_coordinate_is_not_maturity_stage',
    'materialisation_is_plural',
    'no_global_promotion_state',
    'relations_are_independently_evidenced',
    'carrier_replacement_preserves_edge_identity'
  ]) assert(rules[invariant] === true, `Missing governing invariant: ${invariant}`);
  assert(rules.external_participant_in_lineage === false, 'External participant leaked into lineage rule');
  assert(rules.endpoint_digest_is_authority === false, 'Digest incorrectly promoted to authority');
  return { seed, sourceSha256: sha256(text) };
}

function compatibilityRelationId(source, token, target) {
  return `compat:${sha256(`${source}\n${token}\n${target}`).slice(0, 24)}`;
}

export class RecurrentSemanticCompiler {
  constructor(seed) {
    this.seed = clone(seed);
    this.interfaces = new Map();
    this.derivations = [];
    this.compatibility = new Map();
    this.cycles = [];
    for (const [id, iface] of Object.entries(seed.base_interfaces ?? {})) {
      this.interfaces.set(id, Object.freeze({ id, kind: 'BASE', accepts: [...new Set(iface.accepts ?? [])].sort(), emits: [...new Set(iface.emits ?? [])].sort() }));
    }
    this.recomputeCompatibility();
  }

  validateRule(rule) {
    assert(Array.isArray(rule.parents) && rule.parents.length === 2, `Rule ${rule.id}: exactly two parents required`);
    for (const parent of rule.parents) assert(this.interfaces.has(parent), `Rule ${rule.id}: unresolved parent ${parent}`);
    for (const edge of rule.compatibility ?? []) {
      const from = this.interfaces.get(edge.from);
      const to = this.interfaces.get(edge.to);
      assert(from && to, `Rule ${rule.id}: compatibility endpoint absent`);
      assert(interfaceHasToken(from, 'emits', edge.token), `Rule ${rule.id}: ${edge.from} does not emit ${edge.token}`);
      const accepted = edge.to_alias ?? edge.token;
      assert(interfaceHasToken(to, 'accepts', accepted), `Rule ${rule.id}: ${edge.to} does not accept ${accepted}`);
    }
  }

  recomputeCompatibility() {
    const interfaces = [...this.interfaces.values()].sort((a, b) => a.id.localeCompare(b.id));
    for (const source of interfaces) {
      for (const target of interfaces) {
        if (source.id === target.id) continue;
        for (const token of source.emits.filter((item) => target.accepts.includes(item)).sort()) {
          const id = compatibilityRelationId(source.id, token, target.id);
          if (!this.compatibility.has(id)) {
            this.compatibility.set(id, Object.freeze({ id, source: source.id, relation: 'EMITS_ACCEPTS_COMPATIBLE', token, target: target.id }));
          }
        }
      }
    }
  }

  compile() {
    const rules = [...(this.seed.semantic_rules ?? [])].sort((a, b) => a.id.localeCompare(b.id));
    const unresolved = new Set(rules.map((rule) => rule.id));
    let cycle = 0;
    while (unresolved.size > 0) {
      cycle += 1;
      const admitted = [];
      const beforeCompatibility = this.compatibility.size;
      for (const rule of rules) {
        if (!unresolved.has(rule.id)) continue;
        if (!rule.parents.every((parent) => this.interfaces.has(parent))) continue;
        this.validateRule(rule);
        assert(!this.interfaces.has(rule.id), `Semantic collision: ${rule.id}`);
        const child = Object.freeze({
          id: rule.id,
          kind: 'IL_LLM_DERIVED',
          parents: [...rule.parents],
          function: String(rule.function),
          accepts: [...new Set(rule.accepts ?? [])].sort(),
          emits: [...new Set(rule.emits ?? [])].sort(),
          admitted_cycle: cycle,
          lineage_root: this.seed.lineage_root
        });
        this.interfaces.set(child.id, child);
        this.derivations.push(child);
        unresolved.delete(rule.id);
        admitted.push(child.id);
        this.recomputeCompatibility();
      }
      this.cycles.push(Object.freeze({
        cycle,
        admitted: [...admitted].sort(),
        active_state_size: this.interfaces.size,
        compatibility_added: this.compatibility.size - beforeCompatibility
      }));
      if (admitted.length === 0) break;
      assert(cycle <= rules.length + 1, 'Semantic recurrence exceeded finite rule bound');
    }
    const unresolvedRules = rules.filter((rule) => unresolved.has(rule.id)).map((rule) => ({ id: rule.id, parents: rule.parents }));
    assert(unresolvedRules.length === 0, `Unresolved semantic rules: ${unresolvedRules.map((item) => item.id).join(',')}`);
    const terminal = this.interfaces.get('CONTINUOUS_KEDDEH_EDGE');
    assert(terminal, 'CONTINUOUS_KEDDEH_EDGE not derivable');
    return Object.freeze({
      schema: 'kex.braink.keddeh-edge.semantic-compile.v2',
      seed: this.seed.seed,
      edge_coordinate: this.seed.edge_coordinate,
      lineage_root: this.seed.lineage_root,
      derivation_model: 'RECURRENT_FIXED_POINT',
      derived_children_reenter_active_state: true,
      cycles: this.cycles.map(clone),
      derivations: this.derivations.slice().sort((a, b) => a.id.localeCompare(b.id)).map(clone),
      compatibility_relations: [...this.compatibility.values()].sort((a, b) => a.id.localeCompare(b.id)).map(clone),
      active_state_count: this.interfaces.size,
      terminal: clone(terminal),
      state: 'RELATIONAL_FIXED_POINT_CLOSED'
    });
  }
}

class ReceiptLedger {
  constructor(edgeCoordinate) { this.edgeCoordinate = edgeCoordinate; this.entries = []; }
  append(event, payload = {}) {
    const previous = this.entries.at(-1)?.integrity_sha256 ?? null;
    const core = { seq: this.entries.length + 1, edge: this.edgeCoordinate, event, previous_integrity_sha256: previous, payload: clone(payload) };
    const entry = Object.freeze({ ...core, integrity_sha256: sha256(canonicalJson(core)), digest_is_authority: false });
    this.entries.push(entry);
    return entry;
  }
  snapshot() { return this.entries.map(clone); }
  verify() {
    for (let i = 0; i < this.entries.length; i += 1) {
      const entry = this.entries[i];
      const expectedPrevious = i === 0 ? null : this.entries[i - 1].integrity_sha256;
      if (entry.previous_integrity_sha256 !== expectedPrevious) return false;
      const core = { seq: entry.seq, edge: entry.edge, event: entry.event, previous_integrity_sha256: entry.previous_integrity_sha256, payload: entry.payload };
      if (sha256(canonicalJson(core)) !== entry.integrity_sha256) return false;
    }
    return true;
  }
}

class RelationGraph {
  constructor(edgeCoordinate, relationTypes, ledger) {
    this.edgeCoordinate = edgeCoordinate;
    this.relationTypes = relationTypes;
    this.ledger = ledger;
    this.relations = new Map();
  }
  relationId(source, relation, target) {
    return `relation:${sha256(`${source}\n${relation}\n${target}`).slice(0, 32)}`;
  }
  assertRelation(input) {
    const source = normalizeCoordinate(input.source, 'RELATION_SOURCE');
    const target = normalizeCoordinate(input.target, 'RELATION_TARGET');
    const relation = normalizeCoordinate(input.relation, 'RELATION_TYPE').toUpperCase();
    const relationSpec = this.relationTypes[relation];
    assert(relationSpec, `UNKNOWN_RELATION_TYPE:${relation}`);
    const id = this.relationId(source, relation, target);
    const existing = this.relations.get(id);
    if (existing) {
      if (input.state && existing.state !== input.state) existing.state = input.state;
      if (input.authority && !existing.authorities.includes(input.authority)) existing.authorities.push(input.authority);
      if (input.evidence) existing.evidence.push(clone(input.evidence));
      this.ledger.append('RELATION_REASSERT', { id, source, relation, target, state: existing.state });
      return clone(existing);
    }
    const record = {
      id, source, relation, target,
      class: relationSpec.class,
      state: String(input.state ?? 'DEFINED'),
      lineage_root: input.lineage_root ?? null,
      target_in_kex_lineage: relation === 'DERIVES',
      authorities: input.authority ? [String(input.authority)] : [],
      evidence: input.evidence ? [clone(input.evidence)] : [],
      observations: []
    };
    if (relation !== 'DERIVES') record.target_in_kex_lineage = false;
    this.relations.set(id, record);
    this.ledger.append('RELATION_ASSERT', { id, source, relation, target, class: record.class, state: record.state });
    return clone(record);
  }
  observe(relationId, observation) {
    const relation = this.relations.get(relationId);
    assert(relation, `RELATION_NOT_FOUND:${relationId}`);
    const observer = normalizeCoordinate(observation.observer, 'OBSERVER');
    const itemCore = {
      observer,
      state: String(observation.state ?? 'OBSERVED'),
      authority: observation.authority ? String(observation.authority) : null,
      freshness: observation.freshness ? String(observation.freshness) : null,
      evidence: observation.evidence ? clone(observation.evidence) : null
    };
    const item = { id: `observation:${sha256(canonicalJson({ relation_id: relationId, ...itemCore })).slice(0, 32)}`, ...itemCore };
    if (!relation.observations.some((existing) => existing.id === item.id)) relation.observations.push(item);
    this.ledger.append('RELATION_OBSERVED', { relation_id: relationId, observation_id: item.id, observer, state: item.state });
    return clone(item);
  }
  snapshot() {
    return [...this.relations.values()].map((relation) => ({
      ...clone(relation),
      authorities: [...relation.authorities].sort(),
      evidence: relation.evidence.map(clone),
      observations: relation.observations.slice().sort((a, b) => a.id.localeCompare(b.id)).map(clone)
    })).sort((a, b) => a.id.localeCompare(b.id));
  }
}

function indexRoutes(seed) {
  const byHost = new Map();
  for (const binding of seed.domain_space?.bindings ?? []) {
    const host = normalizeHost(binding.host);
    assert(!byHost.has(host), `Duplicate host binding: ${host}`);
    const routes = (binding.routes ?? []).map((route) => ({
      prefix: normalizePath(route.prefix),
      methods: [...new Set((route.methods ?? []).map(normalizeMethod))].sort(),
      coordinate: String(route.coordinate)
    })).sort((a, b) => b.prefix.length - a.prefix.length || a.prefix.localeCompare(b.prefix));
    byHost.set(host, Object.freeze({ host, routes }));
  }
  return byHost;
}

export class KeddehEdgeRuntimeV2 {
  constructor(seedPath = DEFAULT_SEED) {
    const loaded = loadSeed(seedPath);
    this.seedPath = seedPath;
    this.seed = loaded.seed;
    this.seedSha256 = loaded.sourceSha256;
    this.semantic = new RecurrentSemanticCompiler(this.seed).compile();
    this.routeIndex = indexRoutes(this.seed);
    this.ledger = new ReceiptLedger(this.seed.edge_coordinate);
    this.graph = new RelationGraph(this.seed.edge_coordinate, this.seed.relation_types ?? {}, this.ledger);
    this.server = null;
    this.boundAddress = null;
    this.ledger.append('SEED', { seed: this.seed.seed, seed_sha256: this.seedSha256, lineage_root: this.seed.lineage_root });
    this.installSemanticGraph();
    this.installDomainGraph();
  }

  installSemanticGraph() {
    for (const derivation of this.semantic.derivations) {
      for (const parent of derivation.parents) {
        this.graph.assertRelation({ source: parent, relation: 'DERIVES', target: derivation.id, lineage_root: this.seed.lineage_root, state: 'DERIVED' });
      }
    }
    for (const relation of this.semantic.compatibility_relations) {
      this.graph.assertRelation({ source: relation.source, relation: 'EMITS_ACCEPTS_COMPATIBLE', target: relation.target, state: 'COMPATIBLE', evidence: { token: relation.token } });
    }
  }

  installDomainGraph() {
    for (const binding of this.seed.domain_space?.bindings ?? []) {
      this.graph.assertRelation({ source: this.seed.edge_coordinate, relation: 'BINDS_DOMAIN', target: `domain://${normalizeHost(binding.host)}`, state: 'DEFINED' });
    }
  }

  relate(input) { return this.graph.assertRelation(input); }
  observe(relationId, observation) { return this.graph.observe(relationId, observation); }

  materialise(target, { authority = null, observer = null, state = 'OBSERVED', evidence = null } = {}) {
    const relation = this.relate({ source: this.seed.edge_coordinate, relation: 'MATERIALISES_ON', target, authority, state, evidence });
    if (observer) this.observe(relation.id, { observer, state, authority, evidence });
    return relation;
  }

  resolveRequest(descriptor) {
    const host = normalizeHost(descriptor.host);
    const pathValue = normalizePath(descriptor.path);
    const method = normalizeMethod(descriptor.method);
    const transport = String(descriptor.transport ?? 'HTTP').toUpperCase();
    const sni = descriptor.sni == null ? null : normalizeHost(descriptor.sni);
    if (descriptor.requireSni === true || transport.includes('TLS')) {
      if (!sni) throw new Error('SNI_REQUIRED');
      if (sni !== host) throw new Error('SNI_HOST_MISMATCH');
    }
    const binding = this.routeIndex.get(host);
    if (!binding) throw new Error('DOMAIN_BINDING_NOT_FOUND');
    const route = binding.routes.find((candidate) => candidate.methods.includes(method) && (candidate.prefix === '/' || pathValue === candidate.prefix || pathValue.startsWith(`${candidate.prefix}/`)));
    if (!route) throw new Error('SERVICE_ROUTE_NOT_FOUND');
    const resolution = Object.freeze({
      schema: 'kex.braink.keddeh-edge.resolution.v2',
      edge: this.seed.edge_coordinate,
      ingress: this.seed.finite_ingress.id,
      lineage_root: this.seed.lineage_root,
      transport, host, sni, method, path: pathValue,
      matched_prefix: route.prefix,
      coordinate: route.coordinate,
      carrier_in_lineage: false,
      state: 'KEX_COORDINATE_RESOLVED'
    });
    const traversal = this.relate({ source: this.seed.finite_ingress.id, relation: 'TRAVERSES', target: route.coordinate, state: 'RESOLVED', evidence: { host, path: pathValue, method, transport } });
    this.observe(traversal.id, { observer: descriptor.observer ?? 'observer://runtime', state: 'OBSERVED', evidence: { resolution: clone(resolution) } });
    this.ledger.append('RESOLVE', resolution);
    return resolution;
  }

  dispatch(descriptor) {
    const resolution = this.resolveRequest(descriptor);
    const response = Object.freeze({
      schema: 'kex.braink.keddeh-edge.response.v2',
      edge: this.seed.edge_coordinate,
      coordinate: resolution.coordinate,
      status: 200,
      content_type: 'application/json',
      body: {
        state: 'KEX_EDGE_RELATION_EXECUTED',
        edge: this.seed.edge_coordinate,
        coordinate: resolution.coordinate,
        request: { host: resolution.host, method: resolution.method, path: resolution.path }
      }
    });
    this.ledger.append('DISPATCH', { coordinate: response.coordinate, status: response.status });
    return { resolution, response };
  }

  resolveEdgeState() {
    const relations = this.graph.snapshot();
    const byType = {};
    const observers = new Set();
    for (const relation of relations) {
      byType[relation.relation] = (byType[relation.relation] ?? 0) + 1;
      for (const observation of relation.observations) observers.add(observation.observer);
    }
    return Object.freeze({
      schema: 'kex.braink.keddeh-edge.relational-state.v2',
      edge: this.seed.edge_coordinate,
      lineage_root: this.seed.lineage_root,
      semantic_state: this.semantic.state,
      terminal_semantic_capability: this.semantic.terminal.id,
      relation_count: relations.length,
      relation_counts: stable(byType),
      observer_coordinates: [...observers].sort(),
      relations,
      global_maturity_state: null,
      rule: 'Relations retain independent state/evidence; observer location is not a maturity stage.'
    });
  }

  stateSnapshot() {
    const routeState = [...this.routeIndex.values()].map(clone).sort((a, b) => a.host.localeCompare(b.host));
    const core = {
      schema: 'kex.braink.keddeh-edge.snapshot.v2',
      seed: this.seed.seed,
      seed_sha256: this.seedSha256,
      edge_coordinate: this.seed.edge_coordinate,
      lineage_root: this.seed.lineage_root,
      semantic_state: this.semantic.state,
      semantic_capabilities: this.semantic.derivations.map((item) => item.id).sort(),
      route_state: routeState,
      external_participant_in_lineage: false
    };
    return Object.freeze({ ...core, integrity_sha256: sha256(canonicalJson(core)), digest_is_authority: false });
  }

  verifyContinuity(snapshot, replacementMaterialisation = null) {
    const now = this.stateSnapshot();
    const invariantFields = ['seed_sha256', 'edge_coordinate', 'lineage_root', 'semantic_state'];
    const identityEqual = invariantFields.every((field) => now[field] === snapshot[field]);
    const semanticEqual = canonicalJson(now.semantic_capabilities) === canonicalJson(snapshot.semantic_capabilities);
    const routeEqual = canonicalJson(now.route_state) === canonicalJson(snapshot.route_state);
    let replacementRelation = null;
    if (replacementMaterialisation && identityEqual && semanticEqual && routeEqual) {
      replacementRelation = this.relate({ source: this.seed.edge_coordinate, relation: 'REHYDRATES_TO', target: replacementMaterialisation, state: 'CONTINUITY_VERIFIED' });
    }
    const result = Object.freeze({
      schema: 'kex.braink.keddeh-edge.continuity.v2',
      edge: this.seed.edge_coordinate,
      state: identityEqual && semanticEqual && routeEqual ? 'EDGE_IDENTITY_CONTINUITY_PRESERVED' : 'EDGE_CONTINUITY_DIVERGED',
      identity_equal: identityEqual,
      semantic_equal: semanticEqual,
      route_equal: routeEqual,
      replacement_materialisation: replacementMaterialisation,
      replacement_relation_id: replacementRelation?.id ?? null
    });
    this.ledger.append('CONTINUITY_VERIFY', result);
    return result;
  }

  async startLocal({ host = '127.0.0.1', port = 0 } = {}) {
    if (this.server) throw new Error('EDGE_ALREADY_STARTED');
    this.server = http.createServer((req, res) => {
      try {
        const result = this.dispatch({ transport: 'HTTP', host: req.headers.host, method: req.method, path: req.url, observer: 'observer://loopback-client' });
        const body = JSON.stringify(result.response.body);
        res.writeHead(200, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body), 'x-kex-edge': this.seed.edge_coordinate, 'x-kex-coordinate': result.resolution.coordinate });
        res.end(body);
      } catch (error) {
        const status = ['DOMAIN_BINDING_NOT_FOUND', 'SERVICE_ROUTE_NOT_FOUND'].includes(error.message) ? 404 : 400;
        const body = JSON.stringify({ state: 'EDGE_REJECTED', error: error.message, edge: this.seed.edge_coordinate });
        res.writeHead(status, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) });
        res.end(body);
      }
    });
    await new Promise((resolve, reject) => { this.server.once('error', reject); this.server.listen(port, host, resolve); });
    this.boundAddress = this.server.address();
    const materialisation = `node://process/${process.pid}/http/${this.boundAddress.address}:${this.boundAddress.port}`;
    this.materialise(materialisation, { authority: 'authority://os-process', observer: `observer://process/${process.pid}`, evidence: { pid: process.pid } });
    const ingress = this.relate({ source: this.seed.edge_coordinate, relation: 'ACCEPTS_AT', target: `transport://http/${this.boundAddress.address}:${this.boundAddress.port}`, authority: 'authority://os-socket-bind', state: 'OBSERVED' });
    this.observe(ingress.id, { observer: `observer://process/${process.pid}`, state: 'OBSERVED', evidence: { address: clone(this.boundAddress) } });
    return clone(this.boundAddress);
  }

  async stopLocal() {
    if (!this.server) return;
    const server = this.server;
    this.server = null;
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    this.ledger.append('INGRESS_STOPPED', { state: 'STOPPED', address: this.boundAddress });
  }

  proofPacket() {
    return Object.freeze({
      schema: 'kex.braink.keddeh-edge.proof-packet.v2',
      edge: this.seed.edge_coordinate,
      lineage_root: this.seed.lineage_root,
      semantic_compile: clone(this.semantic),
      state_snapshot: clone(this.stateSnapshot()),
      relational_state: clone(this.resolveEdgeState()),
      ledger_valid: this.ledger.verify(),
      ledger: this.ledger.snapshot(),
      claim_boundary: 'Evidence is attached to individual relations/traversals. No whole-edge maturity or promotion verdict is generated.'
    });
  }
}

export function compileEdgeV2(seedPath = DEFAULT_SEED) {
  const loaded = loadSeed(seedPath);
  return new RecurrentSemanticCompiler(loaded.seed).compile();
}

function parseArgs(argv) {
  const out = { seed: DEFAULT_SEED, command: 'compile' };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--seed') out.seed = path.resolve(argv[++i]);
    else if (arg === '--compile') out.command = 'compile';
    else if (arg === '--snapshot') out.command = 'snapshot';
    else if (arg === '--state') out.command = 'state';
    else if (arg === '--proof') out.command = 'proof';
    else throw new Error(`Unknown argument: ${arg}`);
  }
  return out;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = parseArgs(process.argv.slice(2));
    const runtime = new KeddehEdgeRuntimeV2(args.seed);
    const output = args.command === 'compile' ? runtime.semantic : args.command === 'snapshot' ? runtime.stateSnapshot() : args.command === 'state' ? runtime.resolveEdgeState() : runtime.proofPacket();
    process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`KEDDEH_EDGE_V2_FAILED: ${error.message}\n`);
    process.exitCode = 1;
  }
}
