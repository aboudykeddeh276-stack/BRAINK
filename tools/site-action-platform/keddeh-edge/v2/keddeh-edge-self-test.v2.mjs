#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import http from 'node:http';
import https from 'node:https';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { KeddehEdgeRuntimeV2, compileEdgeV2, loadSeed } from './keddeh-edge-runtime.v2.mjs';
import { startEdgeNodeV2 } from './keddeh-edge-node.v2.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SEED = path.join(HERE, 'keddeh-edge.seed.v2.json');
const OUT = path.join(HERE, 'keddeh-edge-test-receipt.v2.json');

function localRequest({ address, port, host, path: requestPath = '/', method = 'GET' }) {
  return new Promise((resolve, reject) => {
    const req = http.request({ hostname: address, port, path: requestPath, method, headers: { Host: host } }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        let body;
        try { body = JSON.parse(text); } catch { body = text; }
        resolve({ status: res.statusCode, headers: res.headers, body });
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function tlsRequest({ address, port, servername, host, path: requestPath = '/', method = 'GET' }) {
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname: address, port, path: requestPath, method, servername, rejectUnauthorized: false, headers: { Host: host } }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        let body;
        try { body = JSON.parse(text); } catch { body = text; }
        resolve({ status: res.statusCode, headers: res.headers, body });
      });
    });
    req.on('error', reject);
    req.end();
  });
}

const tests = [];
async function test(id, fn) {
  const started = Date.now();
  try { tests.push({ id, pass: true, detail: (await fn()) ?? null, duration_ms: Date.now() - started }); }
  catch (error) { tests.push({ id, pass: false, error: error.stack ?? error.message, duration_ms: Date.now() - started }); }
}

await test('T01_RECURRENT_COMPILER_REACHES_FIXED_POINT', () => {
  const compiled = compileEdgeV2(SEED);
  assert.equal(compiled.state, 'RELATIONAL_FIXED_POINT_CLOSED');
  assert.equal(compiled.derivations.length, 9);
  assert.equal(compiled.terminal.id, 'CONTINUOUS_KEDDEH_EDGE');
  assert.ok(compiled.cycles.length > 1);
  assert.ok(compiled.terminal.admitted_cycle > 1);
  return { terminal: compiled.terminal.id, cycles: compiled.cycles.length, admitted_cycle: compiled.terminal.admitted_cycle };
});

await test('T02_SEMANTIC_RULE_ORDER_DOES_NOT_CHANGE_RESULT', () => {
  const { seed } = loadSeed(SEED);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'keddeh-edge-rule-order-'));
  const reversed = structuredClone(seed);
  reversed.semantic_rules.reverse();
  const altered = path.join(dir, 'seed.json');
  fs.writeFileSync(altered, JSON.stringify(reversed, null, 2));
  const a = compileEdgeV2(SEED);
  const b = compileEdgeV2(altered);
  assert.deepEqual(a.derivations.map((x) => x.id), b.derivations.map((x) => x.id));
  assert.deepEqual(a.compatibility_relations, b.compatibility_relations);
  assert.equal(a.terminal.id, b.terminal.id);
  return { derivations_equal: true, compatibility_equal: true };
});

await test('T03_DERIVED_CHILDREN_REENTER_ACTIVE_RELATION_SPACE', () => {
  const compiled = compileEdgeV2(SEED);
  const derivedIds = new Set(compiled.derivations.map((x) => x.id));
  const derivedCompatibility = compiled.compatibility_relations.filter((r) => derivedIds.has(r.source) || derivedIds.has(r.target));
  assert.ok(derivedCompatibility.length > 0);
  assert.ok(compiled.compatibility_relations.some((r) => r.source === 'EDGE_ROUTE_INGRESS' && r.target === 'API_SERVER' && r.token === 'route.selection'));
  return { derived_compatibility_relations: derivedCompatibility.length };
});

await test('T04_NO_GLOBAL_PROMOTION_OR_GATE_MODEL_IN_V2', () => {
  const seed = JSON.parse(fs.readFileSync(SEED, 'utf8'));
  const runtimeSource = fs.readFileSync(path.join(HERE, 'keddeh-edge-runtime.v2.mjs'), 'utf8');
  assert.equal(Object.hasOwn(seed, 'promotion_gates'), false);
  assert.equal(runtimeSource.includes('evaluatePublicPromotion('), false);
  assert.equal(runtimeSource.includes("state:pass?'PUBLIC_EDGE_PROMOTED'"), false);
  return { promotion_gates_absent: true, global_promotion_evaluator_absent: true };
});

await test('T05_ONE_EDGE_IDENTITY_SUPPORTS_PLURAL_MATERIALISATIONS', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  edge.materialise('carrier://alpha', { observer: 'observer://alpha' });
  edge.materialise('carrier://beta', { observer: 'observer://beta' });
  const state = edge.resolveEdgeState();
  const mats = state.relations.filter((r) => r.relation === 'MATERIALISES_ON');
  assert.equal(mats.length, 2);
  assert.ok(mats.every((r) => r.source === 'KEX://EDGE/KEDDEH'));
  assert.equal(state.edge, 'KEX://EDGE/KEDDEH');
  return { edge: state.edge, materialisations: mats.map((r) => r.target) };
});

await test('T06_OBSERVER_COORDINATES_COEXIST_WITHOUT_STAGE_STATE', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  for (const observer of ['observer://local/process', 'observer://remote/peer', 'observer://internet/client']) {
    const relation = edge.relate({ source: edge.seed.edge_coordinate, relation: 'OBSERVED_BY', target: observer, state: 'OBSERVED' });
    edge.observe(relation.id, { observer, state: 'OBSERVED' });
  }
  const state = edge.resolveEdgeState();
  assert.equal(state.global_maturity_state, null);
  assert.ok(state.observer_coordinates.includes('observer://local/process'));
  assert.ok(state.observer_coordinates.includes('observer://remote/peer'));
  assert.ok(state.observer_coordinates.includes('observer://internet/client'));
  return { observers: state.observer_coordinates, global_maturity_state: state.global_maturity_state };
});

await test('T07_AUTHORITY_DNS_TLS_TRANSPORT_RELATIONS_ARE_ORDER_INDEPENDENT', () => {
  const definitions = [
    ['AUTHORITY_HELD_BY', 'authority://registrar/current'],
    ['PROJECTS_DNS', 'dns-authority://current'],
    ['BINDS_IDENTITY', 'tls-identity://keddeh.com'],
    ['ACCEPTS_AT', 'transport://internet/443']
  ];
  const build = (items) => {
    const edge = new KeddehEdgeRuntimeV2(SEED);
    for (const [relation, target] of items) edge.relate({ source: edge.seed.edge_coordinate, relation, target, state: 'DEFINED' });
    return edge.resolveEdgeState().relations.filter((r) => definitions.some(([name]) => name === r.relation)).map((r) => [r.source, r.relation, r.target]);
  };
  assert.deepEqual(build(definitions), build([...definitions].reverse()));
  return { order_independent: true, peer_relation_count: definitions.length };
});

await test('T08_EVIDENCE_IS_ATTACHED_PER_RELATION_AND_MULTI_OBSERVER', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  const relation = edge.relate({ source: edge.seed.edge_coordinate, relation: 'PROJECTS_DNS', target: 'dns-authority://example', state: 'DEFINED' });
  edge.observe(relation.id, { observer: 'observer://resolver/a', state: 'OBSERVED', freshness: 't1', evidence: { answer: 'A' } });
  edge.observe(relation.id, { observer: 'observer://resolver/b', state: 'OBSERVED', freshness: 't1', evidence: { answer: 'A' } });
  const resolved = edge.resolveEdgeState().relations.find((r) => r.id === relation.id);
  assert.equal(resolved.observations.length, 2);
  assert.deepEqual(resolved.observations.map((o) => o.observer).sort(), ['observer://resolver/a', 'observer://resolver/b']);
  return { relation_id: relation.id, observations: resolved.observations.length };
});

await test('T09_FINITE_INGRESS_MULTIPLEXES_LOGICAL_COORDINATES', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  const braink = edge.resolveRequest({ transport: 'TLS_HTTPS', sni: 'braink.keddeh.com', host: 'braink.keddeh.com', path: '/chat/thread/1', method: 'GET' });
  const kex = edge.resolveRequest({ transport: 'TLS_HTTPS', sni: 'kex.keddeh.com', host: 'kex.keddeh.com', path: '/proof/packet', method: 'POST' });
  assert.equal(braink.ingress, kex.ingress);
  assert.equal(braink.coordinate, 'KEX://API/BRAINK/CHAT');
  assert.equal(kex.coordinate, 'KEX://DOMAIN-SPACE/keddeh/kex/proof');
  return { ingress: braink.ingress, coordinates: [braink.coordinate, kex.coordinate] };
});

await test('T10_LONGEST_PREFIX_ROUTE_WINS', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  const result = edge.resolveRequest({ host: 'keddeh.com', path: '/systems/status', method: 'GET' });
  assert.equal(result.matched_prefix, '/systems');
  return { matched_prefix: result.matched_prefix, coordinate: result.coordinate };
});

await test('T11_SNI_HOST_MISMATCH_REJECTED', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  assert.throws(() => edge.resolveRequest({ transport: 'TLS_HTTPS', sni: 'kex.keddeh.com', host: 'braink.keddeh.com', path: '/chat', method: 'GET' }), /SNI_HOST_MISMATCH/);
  return { rejected: true };
});

await test('T12_UNKNOWN_DOMAIN_AND_METHOD_REJECTED', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  assert.throws(() => edge.resolveRequest({ host: 'unknown.keddeh.com', path: '/', method: 'GET' }), /DOMAIN_BINDING_NOT_FOUND/);
  assert.throws(() => edge.resolveRequest({ host: 'braink.keddeh.com', path: '/state', method: 'DELETE' }), /SERVICE_ROUTE_NOT_FOUND/);
  return { unknown_domain_rejected: true, method_rejected: true };
});

await test('T13_REAL_LOOPBACK_SOCKET_ROUTES_THROUGH_SAME_EDGE_IDENTITY', async () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  const bound = await edge.startLocal();
  try {
    const response = await localRequest({ address: bound.address, port: bound.port, host: 'braink.keddeh.com', path: '/chat' });
    assert.equal(response.status, 200);
    assert.equal(response.headers['x-kex-edge'], 'KEX://EDGE/KEDDEH');
    assert.equal(response.headers['x-kex-coordinate'], 'KEX://API/BRAINK/CHAT');
    assert.equal(response.body.state, 'KEX_EDGE_RELATION_EXECUTED');
    return { address: bound.address, port: bound.port, edge: response.headers['x-kex-edge'], coordinate: response.body.coordinate };
  } finally { await edge.stopLocal(); }
});

await test('T14_REAL_LOOPBACK_SOCKET_FAILS_CLOSED_FOR_UNKNOWN_HOST', async () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  const bound = await edge.startLocal();
  try {
    const response = await localRequest({ address: bound.address, port: bound.port, host: 'unknown.keddeh.com', path: '/' });
    assert.equal(response.status, 404);
    assert.equal(response.body.error, 'DOMAIN_BINDING_NOT_FOUND');
    return { status: response.status, error: response.body.error };
  } finally { await edge.stopLocal(); }
});

await test('T15_LEDGER_IS_MONOTONIC_AND_CHAIN_VALID', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  edge.resolveRequest({ host: 'kex.keddeh.com', path: '/runtime', method: 'GET' });
  const proof = edge.proofPacket();
  assert.equal(proof.ledger_valid, true);
  for (let i = 0; i < proof.ledger.length; i += 1) assert.equal(proof.ledger[i].seq, i + 1);
  assert.match(proof.claim_boundary, /individual relations\/traversals/);
  return { entries: proof.ledger.length, ledger_valid: proof.ledger_valid };
});

await test('T16_CONTINUITY_PRESERVES_IDENTITY_ACROSS_REPLACEMENT_MATERIALISATION', () => {
  const first = new KeddehEdgeRuntimeV2(SEED);
  first.materialise('carrier://alpha', { observer: 'observer://alpha' });
  const snapshot = first.stateSnapshot();
  const second = new KeddehEdgeRuntimeV2(SEED);
  second.materialise('carrier://beta', { observer: 'observer://beta' });
  const receipt = second.verifyContinuity(snapshot, 'carrier://beta');
  assert.equal(receipt.state, 'EDGE_IDENTITY_CONTINUITY_PRESERVED');
  assert.equal(receipt.identity_equal, true);
  assert.equal(receipt.route_equal, true);
  const relation = second.resolveEdgeState().relations.find((r) => r.id === receipt.replacement_relation_id);
  assert.equal(relation.relation, 'REHYDRATES_TO');
  return receipt;
});

await test('T17_EXTERNAL_PARTICIPANTS_NEVER_ENTER_KEX_LINEAGE_BY_BINDING', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  for (const [relation, target] of [
    ['MATERIALISES_ON', 'carrier://external'],
    ['AUTHORITY_HELD_BY', 'authority://registrar'],
    ['PROJECTS_DNS', 'dns-authority://provider'],
    ['BINDS_IDENTITY', 'tls-identity://ca-issued'],
    ['ACCEPTS_AT', 'transport://internet']
  ]) edge.relate({ source: edge.seed.edge_coordinate, relation, target });
  const bound = edge.resolveEdgeState().relations.filter((r) => r.source === edge.seed.edge_coordinate && r.relation !== 'BINDS_DOMAIN');
  assert.ok(bound.every((r) => r.target_in_kex_lineage === false));
  return { checked: bound.length, external_in_lineage: false };
});

await test('T18_EDGE_NODE_WRITES_DURABLE_MATERIALISATION_AND_STOP_RECEIPTS', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'keddeh-edge-v2-receipts-'));
  const node = await startEdgeNodeV2({ seed: SEED, bind: '127.0.0.1', port: 0, receiptDir: dir });
  try {
    assert.equal(fs.existsSync(node.bootReceiptPath), true);
    const boot = JSON.parse(fs.readFileSync(node.bootReceiptPath, 'utf8'));
    assert.equal(boot.state, 'MATERIALISATION_OBSERVED');
    assert.ok(boot.materialisation_relation_id);
    assert.ok(boot.ingress_relation_id);
    assert.equal(boot.edge, 'KEX://EDGE/KEDDEH');
  } finally {
    const stopped = await node.stop('SELF_TEST');
    assert.equal(fs.existsSync(stopped.stopReceiptPath), true);
    assert.equal(stopped.stopReceipt.state, 'MATERIALISATION_STOPPED');
  }
  return { durable_materialisation_receipt: true, durable_stop_receipt: true };
});

await test('T19_NATIVE_TLS_NODE_HANDSHAKE_AND_SNI_ROUTING', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'keddeh-edge-v2-tls-'));
  const key = path.join(dir, 'edge.key.pem');
  const cert = path.join(dir, 'edge.cert.pem');
  execFileSync('openssl', ['req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',key,'-out',cert,'-subj','/CN=braink.keddeh.com','-addext','subjectAltName=DNS:braink.keddeh.com,DNS:kex.keddeh.com,DNS:keddeh.com'], { stdio: 'ignore' });
  const node = await startEdgeNodeV2({ seed: SEED, bind: '127.0.0.1', port: 0, tlsCert: cert, tlsKey: key, receiptDir: dir });
  try {
    assert.equal(node.bootReceipt.transport, 'TLS_HTTPS');
    assert.match(node.bootReceipt.tls_certificate.subject_alt_name, /braink\.keddeh\.com/);
    const response = await tlsRequest({ address: node.address.address, port: node.address.port, servername: 'braink.keddeh.com', host: 'braink.keddeh.com', path: '/chat' });
    assert.equal(response.status, 200);
    assert.equal(response.headers['x-kex-edge'], 'KEX://EDGE/KEDDEH');
    assert.equal(response.body.coordinate, 'KEX://API/BRAINK/CHAT');
    const mismatch = await tlsRequest({ address: node.address.address, port: node.address.port, servername: 'kex.keddeh.com', host: 'braink.keddeh.com', path: '/chat' });
    assert.equal(mismatch.status, 400);
    assert.equal(mismatch.body.error, 'SNI_HOST_MISMATCH');
    const tlsRelations = node.runtime.resolveEdgeState().relations.filter((r) => r.relation === 'BINDS_IDENTITY');
    assert.equal(tlsRelations.length, 1);
    return { tls_handshake: true, edge: response.headers['x-kex-edge'], sni_route: response.body.coordinate, mismatch_rejected: true, certificate_scope: 'SELF_SIGNED_TEST_FIXTURE_ONLY' };
  } finally { await node.stop('SELF_TEST'); }
});

await test('T20_RELATIONAL_STATE_HAS_NO_FALSE_LOCAL_REMOTE_PUBLIC_PARTITION', () => {
  const edge = new KeddehEdgeRuntimeV2(SEED);
  edge.materialise('node://local', { observer: 'observer://local' });
  edge.relate({ source: edge.seed.edge_coordinate, relation: 'BRIDGES', target: 'peer://remote', state: 'DEFINED' });
  edge.relate({ source: edge.seed.edge_coordinate, relation: 'ACCEPTS_AT', target: 'transport://public', state: 'DEFINED' });
  const state = edge.resolveEdgeState();
  assert.equal(state.edge, 'KEX://EDGE/KEDDEH');
  assert.equal(state.global_maturity_state, null);
  assert.equal(new Set(state.relations.filter((r) => ['MATERIALISES_ON','BRIDGES','ACCEPTS_AT'].includes(r.relation)).map((r) => r.source)).size, 1);
  return { one_edge_identity: state.edge, relation_spaces_coexist: true };
});

const failed = tests.filter((item) => !item.pass);
const receipt = {
  schema: 'kex.braink.keddeh-edge.self-test-receipt.v2',
  generated_at: new Date().toISOString(),
  seed: SEED,
  tests_run: tests.length,
  passed: tests.length - failed.length,
  failed: failed.length,
  state: failed.length === 0 ? 'RELATIONAL_EDGE_V2_TESTS_PASS' : 'RELATIONAL_EDGE_V2_TESTS_FAIL',
  claim_boundary: 'Tests prove the V2 relational architecture, recurrent IL-LLM closure, plural materialisation semantics, per-relation evidence, local socket execution, TLS fixture execution and continuity invariants. They do not manufacture observations for registrar, authoritative DNS, CA trust, WAN routing, or remote carriers.',
  tests
};
fs.writeFileSync(OUT, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
if (failed.length) process.exitCode = 1;
