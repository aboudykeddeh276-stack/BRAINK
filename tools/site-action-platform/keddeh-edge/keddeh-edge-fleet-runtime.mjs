#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { KeddehEdgeRuntime } from './keddeh-edge-runtime.mjs';
import { fetchGoogleIpAuthority, summarizeGoogleIpAuthority } from './google-ip-authority.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BASE_SEED = path.join(HERE, 'keddeh-edge.seed.v1.json');
const EXTENSION = path.join(HERE, 'keddeh-edge.fleet-extension.v2.json');

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function assert(condition, message) { if (!condition) throw new Error(message); }

export function composeFleetSeed(basePath = BASE_SEED, extensionPath = EXTENSION) {
  const base = JSON.parse(fs.readFileSync(basePath, 'utf8'));
  const extension = JSON.parse(fs.readFileSync(extensionPath, 'utf8'));
  assert(base.schema === 'kex.braink.keddeh-edge.seed.v1', 'BASE_SEED_SCHEMA_MISMATCH');
  assert(extension.schema === 'kex.braink.keddeh-edge.fleet-extension.v2', 'FLEET_EXTENSION_SCHEMA_MISMATCH');
  assert(extension.parent_seed === base.seed, 'FLEET_PARENT_SEED_MISMATCH');
  assert(extension.rules?.preserve_parent_seed === true, 'PARENT_PRESERVATION_RULE_MISSING');
  assert(extension.rules?.digest_role === 'INTEGRITY_ONLY', 'DIGEST_ROLE_VIOLATION');

  const successor = clone(base);
  successor.schema = base.schema;
  successor.seed = `${base.seed}::FLEET-V2`;
  successor.predecessor = { seed: base.seed, edge_coordinate: base.edge_coordinate };
  successor.successor_relation = 'TYPED_SUCCESSOR_EXTENSION';
  successor.fleet_schema = extension.schema;
  successor.fleet_extension = {
    schema: extension.schema,
    relation: extension.relation,
    authority: extension.authority,
    rules: clone(extension.rules),
    agent_fleet: clone(extension.agent_fleet)
  };

  const existing = new Set((successor.domain_space?.bindings ?? []).map((binding) => String(binding.host).toLowerCase()));
  for (const binding of extension.bindings ?? []) {
    const host = String(binding.host).toLowerCase();
    if (existing.has(host)) throw new Error(`DUPLICATE_DOMAIN_BINDING:${host}`);
    successor.domain_space.bindings.push(clone(binding));
    existing.add(host);
  }

  return successor;
}

export function instantiateFleetRuntime() {
  const seed = composeFleetSeed();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'keddeh-edge-fleet-'));
  const seedPath = path.join(dir, 'keddeh-edge.seed.v2-fleet.json');
  fs.writeFileSync(seedPath, JSON.stringify(seed, null, 2));
  const runtime = new KeddehEdgeRuntime(seedPath);
  return { runtime, seed, seedPath, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

export async function loadGoogleNetworkAuthority(options = {}) {
  const authority = await fetchGoogleIpAuthority(options);
  return {
    authority,
    summary: summarizeGoogleIpAuthority(authority),
    policy: {
      ingress_use: 'EVIDENCE_INPUT_ONLY',
      ip_ownership_is_service_identity: false,
      require_hostname_tls_route_evidence: true,
      refresh_before_authority_sensitive_decision: true
    }
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const googleAuthorityRequested = process.argv.includes('--google-ip-authority');
  const { runtime, seed, cleanup } = instantiateFleetRuntime();
  try {
    const snapshot = runtime.stateSnapshot();
    const output = {
      schema: 'kex.braink.keddeh-edge.fleet-runtime.readback.v3',
      executable_seed_schema: seed.schema,
      fleet_schema: seed.fleet_schema,
      predecessor: seed.predecessor,
      successor_relation: seed.successor_relation,
      edge_coordinate: seed.edge_coordinate,
      binding_count: seed.domain_space.bindings.length,
      hosts: seed.domain_space.bindings.map((binding) => binding.host),
      semantic_state: snapshot.semantic_state,
      terminal_semantic_capability: snapshot.terminal_semantic_capability,
      digest_is_authority: false,
      fleet_agent_rule: seed.fleet_extension.agent_fleet.isolation_rule,
      google_ip_authority: googleAuthorityRequested
        ? (await loadGoogleNetworkAuthority()).summary
        : { state: 'AVAILABLE_ON_DEMAND', flag: '--google-ip-authority' }
    };
    process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
  } finally {
    cleanup();
  }
}
