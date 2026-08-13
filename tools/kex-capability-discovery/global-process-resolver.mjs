#!/usr/bin/env node
import fs from 'node:fs';

const TARGETS = [
  'ONLINE_GLOBAL_BINDING',
  'IOT_GLOBAL_DEVICE_SPACE',
  'WEB3_DISTRIBUTED_STATE_SPACE',
  'WEB4_SEMANTIC_EXECUTION_SPACE',
  'CLOUD_CARRIER_INDEPENDENCE',
  'MESH_GLOBAL_CLOSURE'
];

const p = (stage, deps, evidence, capabilityHints) => Object.freeze({ stage, deps, evidence, capabilityHints });

const P = {
  SOURCE_REMOTE_READBACK: p('ONLINE_GLOBAL_BINDING', [], 'REMOTE_PROVIDER_READBACK', ['GitHub','remote source provider']),
  REMOTE_EXECUTION: p('ONLINE_GLOBAL_BINDING', ['SOURCE_REMOTE_READBACK'], 'REMOTE_EXECUTION_READBACK', ['self-host node','cloud carrier','Sites host']),
  PUBLIC_NAME_AUTHORITY: p('ONLINE_GLOBAL_BINDING', [], 'REGISTRAR_OR_REGISTRY_READBACK', ['registrar','registry']),
  AUTHORITATIVE_DNS: p('ONLINE_GLOBAL_BINDING', ['PUBLIC_NAME_AUTHORITY'], 'INDEPENDENT_AUTHORITATIVE_DNS_READBACK', ['DNS provider','independent resolver']),
  TLS_IDENTITY: p('ONLINE_GLOBAL_BINDING', ['AUTHORITATIVE_DNS','REMOTE_EXECUTION'], 'INDEPENDENT_TLS_CHAIN_READBACK', ['TLS/CA edge','outside-in client']),
  PUBLIC_INGRESS: p('ONLINE_GLOBAL_BINDING', ['REMOTE_EXECUTION','AUTHORITATIVE_DNS','TLS_IDENTITY'], 'OUTSIDE_IN_HTTPS_OR_PROTOCOL_READBACK', ['public ingress','API transport']),
  API_CONTRACT: p('ONLINE_GLOBAL_BINDING', ['PUBLIC_INGRESS'], 'REMOTE_API_CONTRACT_RECEIPT', ['API server','listener resolver']),
  DEVICE_REMOTE_IDENTITY: p('IOT_GLOBAL_DEVICE_SPACE', ['API_CONTRACT'], 'REMOTE_DEVICE_IDENTITY_READBACK', ['IoT device','gateway']),
  DEVICE_TELEMETRY: p('IOT_GLOBAL_DEVICE_SPACE', ['DEVICE_REMOTE_IDENTITY'], 'REMOTE_TELEMETRY_ROUNDTRIP', ['sensor','gateway']),
  DEVICE_COMMAND: p('IOT_GLOBAL_DEVICE_SPACE', ['DEVICE_REMOTE_IDENTITY'], 'REMOTE_COMMAND_ACK', ['actuator','gateway']),
  DEVICE_REJOIN: p('IOT_GLOBAL_DEVICE_SPACE', ['DEVICE_TELEMETRY','DEVICE_COMMAND'], 'OFFLINE_REJOIN_RECEIPT', ['device','gateway']),
  PEER_IDENTITY: p('WEB3_DISTRIBUTED_STATE_SPACE', ['API_CONTRACT'], 'REMOTE_PEER_IDENTITY_READBACK', ['peer','federated node']),
  STATE_EXCHANGE: p('WEB3_DISTRIBUTED_STATE_SPACE', ['PEER_IDENTITY'], 'PEER_VERIFIED_STATE_EXCHANGE', ['peer','state service']),
  DISTRIBUTED_OWNERSHIP: p('WEB3_DISTRIBUTED_STATE_SPACE', ['STATE_EXCHANGE'], 'MULTI_PEER_OWNERSHIP_RECEIPT', ['federated state']),
  SEMANTIC_REMOTE_RESOLUTION: p('WEB4_SEMANTIC_EXECUTION_SPACE', ['API_CONTRACT','STATE_EXCHANGE'], 'REMOTE_KEX_COORDINATE_RESOLUTION', ['resolver','remote node']),
  CROSS_BOUNDARY_DERIVATION: p('WEB4_SEMANTIC_EXECUTION_SPACE', ['SEMANTIC_REMOTE_RESOLUTION'], 'REMOTE_DERIVED_SERVICE_RECEIPT', ['virtual service mesh']),
  COUSIN_CLOSURE_REMOTE: p('WEB4_SEMANTIC_EXECUTION_SPACE', ['CROSS_BOUNDARY_DERIVATION'], 'CROSS_CODEBASE_TYPED_BRIDGE_READBACK', ['typed KEX bridge']),
  REMOTE_REHYDRATION: p('WEB4_SEMANTIC_EXECUTION_SPACE', ['COUSIN_CLOSURE_REMOTE'], 'REMOTE_ROUTE_REHYDRATION_EQUIVALENCE', ['recovery','replacement node']),
  CARRIER_A: p('CLOUD_CARRIER_INDEPENDENCE', ['REMOTE_REHYDRATION'], 'REMOTE_CARRIER_A_READBACK', ['cloud/local carrier A']),
  CARRIER_B: p('CLOUD_CARRIER_INDEPENDENCE', ['CARRIER_A'], 'REMOTE_CARRIER_B_READBACK', ['cloud/local carrier B']),
  CARRIER_REPLACEMENT: p('CLOUD_CARRIER_INDEPENDENCE', ['CARRIER_A','CARRIER_B'], 'SAME_KEX_COORDINATE_REPLACEMENT_RECEIPT', ['carrier failover']),
  PEER_DISCOVERY: p('MESH_GLOBAL_CLOSURE', ['CARRIER_REPLACEMENT','DISTRIBUTED_OWNERSHIP'], 'MULTI_NODE_PEER_DISCOVERY_READBACK', ['mesh peers']),
  CAPABILITY_ADVERTISEMENT: p('MESH_GLOBAL_CLOSURE', ['PEER_DISCOVERY'], 'REMOTE_CAPABILITY_ADVERTISEMENT_READBACK', ['mesh peers']),
  CROSS_CARRIER_ROUTE: p('MESH_GLOBAL_CLOSURE', ['CAPABILITY_ADVERTISEMENT'], 'REMOTE_CROSS_CARRIER_ROUTE_RECEIPT', ['router','bridge','mesh']),
  PARTITION_REJOIN: p('MESH_GLOBAL_CLOSURE', ['CROSS_CARRIER_ROUTE'], 'PARTITION_REJOIN_RECEIPT', ['mesh peers']),
  GLOBAL_FAILOVER: p('MESH_GLOBAL_CLOSURE', ['PARTITION_REJOIN','REMOTE_REHYDRATION'], 'EXTERNALLY_OBSERVED_FAILOVER_RECEIPT', ['replacement peer','outside-in observer']),
  GLOBAL_CLOSURE: p('MESH_GLOBAL_CLOSURE', ['GLOBAL_FAILOVER','COUSIN_CLOSURE_REMOTE','DEVICE_REJOIN'], 'MULTI_BOUNDARY_GLOBAL_CLOSURE_RECEIPT', ['independent observers'])
};

function parseArgs(argv) {
  const out = { target: 'MESH_GLOBAL_CLOSURE', evidence: null, pretty: true };
  for (let i=0;i<argv.length;i++) {
    if (argv[i] === '--target') out.target = argv[++i];
    else if (argv[i] === '--evidence') out.evidence = argv[++i];
    else if (argv[i] === '--compact') out.pretty = false;
    else throw new Error(`Unknown argument ${argv[i]}`);
  }
  if (!TARGETS.includes(out.target)) throw new Error(`Unsupported target ${out.target}`);
  return out;
}

function loadEvidence(path) {
  if (!path) return [];
  const body = JSON.parse(fs.readFileSync(path,'utf8'));
  const entries = Array.isArray(body) ? body : body.observations;
  if (!Array.isArray(entries)) throw new Error('Evidence must be an array or {observations:[...]}');
  return entries;
}

function normalizeObservation(o) {
  if (!o || typeof o !== 'object') throw new Error('Invalid observation');
  if (!P[o.predicate]) throw new Error(`Unknown predicate ${o.predicate}`);
  if (!['OBSERVED','FAILED','UNRESOLVED'].includes(o.state)) throw new Error(`Invalid state for ${o.predicate}`);
  if (o.state === 'OBSERVED' && o.scope !== 'EXTERNAL') throw new Error(`${o.predicate}: global evidence must have scope EXTERNAL`);
  return Object.freeze({ predicate:o.predicate, state:o.state, scope:o.scope ?? 'UNKNOWN', observer:o.observer ?? 'UNSPECIFIED', authority:o.authority ?? 'UNSPECIFIED', receipt:o.receipt ?? null, note:o.note ?? null });
}

const stageRank = stage => TARGETS.indexOf(stage);
const requiredPredicates = target => Object.entries(P).filter(([,v]) => stageRank(v.stage) <= stageRank(target)).map(([k]) => k);

function resolve(target, rawEvidence) {
  const obs = new Map();
  for (const item of rawEvidence.map(normalizeObservation)) obs.set(item.predicate, item);
  const required = new Set(requiredPredicates(target));
  const states = {};
  for (const name of required) states[name] = obs.get(name)?.state ?? 'UNRESOLVED';

  const ready = [], blocked = [], failed = [];
  for (const name of required) {
    const state = states[name];
    if (state === 'OBSERVED') continue;
    if (state === 'FAILED') { failed.push(name); continue; }
    const missing = P[name].deps.filter(d => required.has(d) && states[d] !== 'OBSERVED');
    if (!missing.length) ready.push(name); else blocked.push({ predicate:name, waiting_on:missing });
  }

  const stageView = TARGETS.filter(s => stageRank(s) <= stageRank(target)).map(stage => {
    const names = [...required].filter(n => P[n].stage === stage);
    const observed = names.filter(n => states[n] === 'OBSERVED').length;
    return { stage, observed, total:names.length, complete:observed === names.length };
  });

  const nextActions = ready.map(name => ({ predicate:name, stage:P[name].stage, required_external_evidence:P[name].evidence, capability_hints:P[name].capabilityHints, integration_mode:'LOGICAL_BIND_OR_TYPED_BRIDGE', physical_merge_default:false }));
  const complete = [...required].every(n => states[n] === 'OBSERVED');

  return {
    schema:'kex.global.resolution.v3',
    local_conformance:'INHERENT_ADMISSIBILITY_NOT_A_GLOBAL_STAGE',
    target,
    process_model:'DEPENDENCY_GRAPH_NOT_STAGE_COUNTER',
    source_lineage_preserved:true,
    external_carriers_in_kex_lineage:false,
    digest_is_kex_authority:false,
    required_predicates:[...required],
    observations:Object.fromEntries([...obs].filter(([k]) => required.has(k))),
    stage_view:stageView,
    next_actions:nextActions,
    failed_predicates:failed,
    blocked_predicates:blocked,
    global_state:complete ? 'GLOBAL_TARGET_OBSERVED' : failed.length ? 'GLOBAL_PROCESS_HAS_FAILED_PREDICATES' : 'GLOBAL_PROCESS_INCOMPLETE'
  };
}

const args = parseArgs(process.argv.slice(2));
process.stdout.write(JSON.stringify(resolve(args.target, loadEvidence(args.evidence)), null, args.pretty ? 2 : 0) + '\n');
