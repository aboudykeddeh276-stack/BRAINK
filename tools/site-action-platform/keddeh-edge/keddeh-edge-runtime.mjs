#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_SEED = path.join(HERE, 'keddeh-edge.seed.v1.json');

const sha256 = (value) => crypto.createHash('sha256').update(String(value)).digest('hex');

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map((k) => [k, stable(value[k])]));
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
const interfaceHasToken = (iface, direction, token) => Array.isArray(iface?.[direction]) && iface[direction].includes(token);

function loadSeed(seedPath = DEFAULT_SEED) {
  const text = fs.readFileSync(seedPath, 'utf8');
  const seed = JSON.parse(text);
  assert(seed.schema === 'kex.braink.keddeh-edge.seed.v1', `Unsupported seed schema: ${seed.schema}`);
  assert(seed.governing_rules?.discover_before_derive === true, 'discover_before_derive invariant absent');
  assert(seed.governing_rules?.external_carrier_in_lineage === false, 'external carrier leaked into lineage rule');
  assert(seed.governing_rules?.endpoint_digest_is_authority === false, 'digest incorrectly promoted to authority');
  return { seed, sourceSha256: sha256(text) };
}

export class SemanticEdgeCompiler {
  constructor(seed) {
    this.seed = clone(seed);
    this.interfaces = new Map();
    this.derivations = [];
    for (const [id, iface] of Object.entries(seed.base_interfaces ?? {})) this.interfaces.set(id, Object.freeze({ id, kind: 'BASE', ...clone(iface) }));
  }
  validateCompatibility(step) {
    for (const edge of step.compatibility ?? []) {
      const from = this.interfaces.get(edge.from);
      const to = this.interfaces.get(edge.to);
      assert(from, `Derivation ${step.id}: missing parent/interface ${edge.from}`);
      assert(to, `Derivation ${step.id}: missing parent/interface ${edge.to}`);
      assert(interfaceHasToken(from, 'emits', edge.token), `Derivation ${step.id}: ${edge.from} does not emit ${edge.token}`);
      const acceptedToken = edge.to_alias ?? edge.token;
      assert(interfaceHasToken(to, 'accepts', acceptedToken), `Derivation ${step.id}: ${edge.to} does not accept ${acceptedToken}`);
    }
  }
  compile() {
    for (const step of this.seed.illlm_semantic_derivations ?? []) {
      assert(Array.isArray(step.parents) && step.parents.length === 2, `Derivation ${step.id}: exactly two parents required`);
      for (const parent of step.parents) assert(this.interfaces.has(parent), `Derivation ${step.id}: unresolved parent ${parent}`);
      this.validateCompatibility(step);
      assert(!this.interfaces.has(step.id), `Derivation collision: ${step.id}`);
      const child = Object.freeze({ id: step.id, kind: 'IL_LLM_DERIVED', parents: [...step.parents], function: step.function, accepts: [...new Set(step.accepts ?? [])].sort(), emits: [...new Set(step.emits ?? [])].sort(), relation: 'SEMANTIC_DERIVATION', lineage_root: this.seed.lineage_root });
      this.interfaces.set(step.id, child);
      this.derivations.push(child);
    }
    const terminal = this.interfaces.get('REHYDRATABLE_KEDDEH_EDGE');
    assert(terminal, 'Terminal REHYDRATABLE_KEDDEH_EDGE was not derived');
    return Object.freeze({ schema: 'kex.braink.keddeh-edge.semantic-compile.v1', seed: this.seed.seed, edge_coordinate: this.seed.edge_coordinate, lineage_root: this.seed.lineage_root, external_carrier_in_lineage: false, derivation_count: this.derivations.length, derivations: this.derivations.map(clone), terminal: clone(terminal), state: 'SEMANTIC_EDGE_CLOSED' });
  }
}

class ReceiptLedger {
  constructor(edgeCoordinate) { this.edgeCoordinate = edgeCoordinate; this.entries = []; }
  append(event, payload = {}) {
    const previous = this.entries.at(-1)?.integrity_sha256 ?? null;
    const core = { seq: this.entries.length + 1, edge: this.edgeCoordinate, event, previous_integrity_sha256: previous, payload: clone(payload) };
    const entry = Object.freeze({ ...core, integrity_sha256: sha256(canonicalJson(core)), digest_is_authority: false });
    this.entries.push(entry); return entry;
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

function indexRoutes(seed) {
  const byHost = new Map();
  for (const binding of seed.domain_space?.bindings ?? []) {
    const host = normalizeHost(binding.host);
    assert(!byHost.has(host), `Duplicate host binding: ${host}`);
    const routes = (binding.routes ?? []).map((route) => ({ prefix: normalizePath(route.prefix), methods: [...new Set((route.methods ?? []).map(normalizeMethod))].sort(), coordinate: String(route.coordinate), public_binding_intended: Boolean(binding.public_binding_intended) })).sort((a,b) => b.prefix.length - a.prefix.length || a.prefix.localeCompare(b.prefix));
    byHost.set(host, Object.freeze({ host, routes, public_binding_intended: Boolean(binding.public_binding_intended) }));
  }
  return byHost;
}

export class KeddehEdgeRuntime {
  constructor(seedPath = DEFAULT_SEED) {
    const loaded = loadSeed(seedPath);
    this.seedPath = seedPath; this.seed = loaded.seed; this.seedSha256 = loaded.sourceSha256;
    this.semantic = new SemanticEdgeCompiler(this.seed).compile();
    this.routeIndex = indexRoutes(this.seed);
    this.ledger = new ReceiptLedger(this.seed.edge_coordinate);
    this.server = null; this.boundAddress = null;
    this.ledger.append('SEED', { seed: this.seed.seed, seed_sha256: this.seedSha256, lineage_root: this.seed.lineage_root, capabilities: this.seed.existing_capability_bindings.map((x) => x.id) });
    for (const derivation of this.semantic.derivations) this.ledger.append('IL_LLM_DERIVE', { id: derivation.id, parents: derivation.parents, function: derivation.function });
    this.ledger.append('EDGE_COMPILE', { state: this.semantic.state, terminal: this.semantic.terminal.id });
  }
  resolveRequest(descriptor) {
    const host = normalizeHost(descriptor.host); const pathValue = normalizePath(descriptor.path); const method = normalizeMethod(descriptor.method);
    const transport = String(descriptor.transport ?? 'LOCAL_HTTP').toUpperCase(); const sni = descriptor.sni == null ? null : normalizeHost(descriptor.sni);
    if (transport === 'PUBLIC_TLS' || descriptor.requireSni === true) { if (!sni) throw new Error('SNI_REQUIRED'); if (sni !== host) throw new Error('SNI_HOST_MISMATCH'); }
    const binding = this.routeIndex.get(host); if (!binding) throw new Error('DOMAIN_BINDING_NOT_FOUND');
    const route = binding.routes.find((candidate) => candidate.methods.includes(method) && (candidate.prefix === '/' || pathValue === candidate.prefix || pathValue.startsWith(`${candidate.prefix}/`)));
    if (!route) throw new Error('SERVICE_ROUTE_NOT_FOUND');
    const resolution = Object.freeze({ schema:'kex.braink.keddeh-edge.resolution.v1', edge:this.seed.edge_coordinate, ingress:this.seed.finite_ingress.id, lineage_root:this.seed.lineage_root, transport, host, sni, method, path:pathValue, matched_prefix:route.prefix, coordinate:route.coordinate, public_binding_intended:route.public_binding_intended, carrier_in_lineage:false, state:'KEX_COORDINATE_RESOLVED' });
    this.ledger.append('RESOLVE', resolution); return resolution;
  }
  dispatch(descriptor) {
    const resolution = this.resolveRequest(descriptor);
    const response = Object.freeze({ schema:'kex.braink.keddeh-edge.response.v1', edge:this.seed.edge_coordinate, coordinate:resolution.coordinate, status:200, content_type:'application/json', body:{ state:'LOCAL_EDGE_CONTRACT_EXECUTED', coordinate:resolution.coordinate, request:{host:resolution.host,method:resolution.method,path:resolution.path}, public_claim:false } });
    this.ledger.append('DISPATCH', { coordinate: response.coordinate, status: response.status });
    this.ledger.append('READBACK', { scope:'LOCAL_LOOPBACK', coordinate:response.coordinate, state:'OBSERVED' });
    return { resolution, response };
  }
  evaluatePublicPromotion(evidence = {}) {
    const gates = (this.seed.promotion_gates ?? []).map((gate) => { const receipt = evidence[gate.id]; const pass = Boolean(receipt && receipt.state === 'OBSERVED' && receipt.scope === 'EXTERNAL'); return { ...clone(gate), pass, receipt: receipt ? clone(receipt) : null }; });
    const required = gates.filter((g) => g.required); const pass = required.length > 0 && required.every((g) => g.pass);
    const verdict = Object.freeze({ schema:'kex.braink.keddeh-edge.public-promotion.v1', edge:this.seed.edge_coordinate, pass, state:pass?'PUBLIC_EDGE_PROMOTED':'PUBLIC_EDGE_NOT_PROMOTED', gates });
    this.ledger.append('PUBLIC_PROMOTION_EVALUATED', { pass, failed_gates:gates.filter((g)=>!g.pass).map((g)=>g.id) }); return verdict;
  }
  stateSnapshot() {
    const routeState = [...this.routeIndex.values()].map((binding) => clone(binding));
    const snapshot = { schema:'kex.braink.keddeh-edge.snapshot.v1', seed:this.seed.seed, seed_sha256:this.seedSha256, edge_coordinate:this.seed.edge_coordinate, lineage_root:this.seed.lineage_root, semantic_state:this.semantic.state, terminal_semantic_capability:this.semantic.terminal.id, route_state:routeState, external_carrier_in_lineage:false };
    return Object.freeze({ ...snapshot, integrity_sha256:sha256(canonicalJson(snapshot)), digest_is_authority:false });
  }
  rehydrateEquivalent(snapshot) {
    const now=this.stateSnapshot(); const fields=['seed_sha256','edge_coordinate','lineage_root','semantic_state','terminal_semantic_capability'];
    const scalarEqual=fields.every((field)=>now[field]===snapshot[field]); const routeEqual=canonicalJson(now.route_state)===canonicalJson(snapshot.route_state);
    const result=Object.freeze({schema:'kex.braink.keddeh-edge.rehydration.v1',state:scalarEqual&&routeEqual?'REHYDRATED_EQUIVALENT':'REHYDRATION_DIVERGED',scalar_equal:scalarEqual,route_equal:routeEqual,edge:this.seed.edge_coordinate});
    this.ledger.append('REHYDRATE',result); return result;
  }
  async startLocal({ host='127.0.0.1', port=0 }={}) {
    if (this.server) throw new Error('EDGE_ALREADY_STARTED');
    this.server=http.createServer((req,res)=>{ try { const result=this.dispatch({transport:'LOCAL_HTTP',host:req.headers.host,method:req.method,path:req.url}); const body=JSON.stringify(result.response.body); res.writeHead(200,{'content-type':'application/json','content-length':Buffer.byteLength(body),'x-kex-edge':this.seed.edge_coordinate,'x-kex-coordinate':result.resolution.coordinate}); res.end(body); } catch(error) { const status=['DOMAIN_BINDING_NOT_FOUND','SERVICE_ROUTE_NOT_FOUND'].includes(error.message)?404:400; const body=JSON.stringify({state:'EDGE_REJECTED',error:error.message,public_claim:false}); res.writeHead(status,{'content-type':'application/json','content-length':Buffer.byteLength(body)}); res.end(body); } });
    await new Promise((resolve,reject)=>{this.server.once('error',reject);this.server.listen(port,host,resolve);});
    this.boundAddress=this.server.address(); this.ledger.append('LOCAL_INGRESS_BOUND',{address:this.boundAddress.address,port:this.boundAddress.port,transport:'HTTP_LOOPBACK_ONLY',public_claim:false}); return clone(this.boundAddress);
  }
  async stopLocal() { if (!this.server) return; const server=this.server; this.server=null; await new Promise((resolve,reject)=>server.close((error)=>error?reject(error):resolve())); this.ledger.append('LOCAL_INGRESS_STOPPED',{state:'STOPPED'}); }
  proofPacket() { return Object.freeze({schema:'kex.braink.keddeh-edge.proof-packet.v1',edge:this.seed.edge_coordinate,lineage_root:this.seed.lineage_root,semantic_compile:clone(this.semantic),state_snapshot:clone(this.stateSnapshot()),ledger_valid:this.ledger.verify(),ledger:this.ledger.snapshot(),claim_boundary:'LOCAL deterministic edge contract/runtime evidence only; no public DNS/TLS/ingress claim.'}); }
}

export function compileEdge(seedPath=DEFAULT_SEED){const loaded=loadSeed(seedPath);return new SemanticEdgeCompiler(loaded.seed).compile();}
function parseArgs(argv){const out={seed:DEFAULT_SEED,command:'compile'};for(let i=0;i<argv.length;i+=1){const arg=argv[i];if(arg==='--seed')out.seed=path.resolve(argv[++i]);else if(arg==='--compile')out.command='compile';else if(arg==='--snapshot')out.command='snapshot';else if(arg==='--proof')out.command='proof';else throw new Error(`Unknown argument: ${arg}`);}return out;}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){try{const args=parseArgs(process.argv.slice(2));const runtime=new KeddehEdgeRuntime(args.seed);const output=args.command==='compile'?runtime.semantic:args.command==='snapshot'?runtime.stateSnapshot():runtime.proofPacket();process.stdout.write(`${JSON.stringify(output,null,2)}\n`);}catch(error){process.stderr.write(`KEDDEH_EDGE_FAILED: ${error.message}\n`);process.exitCode=1;}}
