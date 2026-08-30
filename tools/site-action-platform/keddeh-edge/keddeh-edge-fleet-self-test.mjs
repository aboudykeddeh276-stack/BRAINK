#!/usr/bin/env node
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { instantiateFleetRuntime } from './keddeh-edge-fleet-runtime.mjs';

const expected = [
  ['keddeh.com', '/', 'KEX://DOMAIN-SPACE/keddeh/site'],
  ['braink.keddeh.com', '/', 'KEX://DOMAIN-SPACE/keddeh/braink/site'],
  ['kex.keddeh.com', '/', 'KEX://DOMAIN-SPACE/keddeh/kex/site'],
  ['casepath.keddeh.com', '/', 'KEX://DOMAIN-SPACE/keddeh/casepath/site'],
  ['braink.com.au', '/', 'KEX://DOMAIN-SPACE/braink.com.au/site'],
  ['casepath.com.au', '/', 'KEX://DOMAIN-SPACE/casepath.com.au/site'],
  ['claimpath.org', '/', 'KEX://DOMAIN-SPACE/claimpath.org/site'],
  ['braink.store', '/', 'KEX://DOMAIN-SPACE/braink.store/site'],
  ['braink.studio', '/', 'KEX://DOMAIN-SPACE/braink.studio/site']
];

function run() {
  const { runtime, seed, cleanup } = instantiateFleetRuntime();
  const tests = [];
  const test = (id, pass, detail) => tests.push({ id, pass: Boolean(pass), detail });
  try {
    test('PARENT_SEED_PRESERVED', seed.predecessor?.seed === 'KEX-KEDDEH-EDGE-V1', seed.predecessor);
    test('DIGEST_NOT_AUTHORITY', seed.fleet_extension?.rules?.digest_role === 'INTEGRITY_ONLY', seed.fleet_extension?.rules?.digest_role);
    test('FLEET_ISOLATION', seed.fleet_extension?.agent_fleet?.isolation_rule === 'ONE_SITE_ONE_AGENT_FLEET_ONE_CONTINUATION_FRAME_ONE_FAILURE_LEDGER', seed.fleet_extension?.agent_fleet?.isolation_rule);
    test('BINDING_COUNT', seed.domain_space.bindings.length === 9, seed.domain_space.bindings.map((x) => x.host));

    for (const [host, requestPath, coordinate] of expected) {
      try {
        const result = runtime.resolveRequest({ transport: 'LOCAL_HTTP', host, method: 'GET', path: requestPath });
        test(`ROUTE:${host}`, result.coordinate === coordinate, result);
      } catch (error) {
        test(`ROUTE:${host}`, false, error.message);
      }
    }

    let unknownRejected = false;
    try { runtime.resolveRequest({ transport: 'LOCAL_HTTP', host: 'unknown.invalid', method: 'GET', path: '/' }); }
    catch (error) { unknownRejected = error.message === 'DOMAIN_BINDING_NOT_FOUND'; }
    test('UNKNOWN_DOMAIN_TYPED_REJECTION', unknownRejected, 'DOMAIN_BINDING_NOT_FOUND expected');

    const snapshot = runtime.stateSnapshot();
    const rehydration = runtime.rehydrateEquivalent(snapshot);
    test('REHYDRATION_EQUIVALENCE', rehydration.state === 'REHYDRATED_EQUIVALENT', rehydration);
    test('LEDGER_VALID', runtime.ledger.verify(), { entries: runtime.ledger.snapshot().length });

    const pass = tests.every((x) => x.pass);
    return {
      schema: 'kex.braink.keddeh-edge.fleet-self-test.v2',
      state: pass ? 'PASS' : 'FAIL',
      passed: tests.filter((x) => x.pass).length,
      total: tests.length,
      tests,
      public_claim: false,
      failure_semantics: 'FAILURE_IS_TYPED_SIGNAL_FOR_REPAIR'
    };
  } finally {
    cleanup();
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = run();
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.state !== 'PASS') process.exitCode = 1;
}

export { run };
