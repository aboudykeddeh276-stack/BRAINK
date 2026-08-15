#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { ContinuationFrame } from './continuation.mjs';
import { CapabilityResolver } from './capability-resolver.mjs';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'braink-continuation-'));
const registry = path.join(tmp, 'registry.json');
fs.writeFileSync(registry, JSON.stringify({
  capabilities: {
    TEST_RUNTIME: {
      capability_id: 'TEST-CAP-001',
      runtime: 'test-runtime',
      state: 'UNLOCKED'
    }
  }
}));

let frame = new ContinuationFrame({
  id: 'KEX://TEST/CONTINUATION/1',
  taskId: 'TASK-1',
  goal: 'Verify recursive continuation',
  observer: { mode: 'TEST' },
  registers: ['R1=alpha', 'R2=beta'],
  workingMemory: { preserved: true },
  authority: { scope: 'SELF' }
});

const resolver = new CapabilityResolver({ registryPath: registry });
const resolved = resolver.resolve({
  intent: 'test runtime',
  continuation: frame
});
assert.equal(resolved.status, 'RESOLVED');
assert.equal(resolved.method, 'REUSE');
frame = resolved.next;
assert.equal(frame.routeStack.at(-1), 'capability://TEST-CAP-001');

frame = frame.transition({
  route: frame.routeStack.at(-1),
  result: 'PASS',
  evidence: { proof_cursor: 'proof://test/1', status: 'TESTED' }
});
const snapshot = frame.snapshot();
const restored = ContinuationFrame.rehydrate(snapshot);
assert.equal(restored.logicalTime, frame.logicalTime);
assert.deepEqual(restored.registers, frame.registers);
assert.deepEqual(restored.workingMemory, frame.workingMemory);
assert.deepEqual(restored.routeStack, frame.routeStack);
assert.equal(restored.stateRoot, frame.stateRoot);

const unknown = resolver.resolve({ intent: 'nonexistent capability', continuation: restored });
assert.equal(unknown.status, 'UNKNOWN');
assert.equal(unknown.next.stateRoot, restored.stateRoot);

fs.rmSync(tmp, { recursive: true, force: true });
console.log(JSON.stringify({
  status: 'PASS',
  tests: 7,
  assertions: [
    'capability discovery precedes derivation',
    'resolved capability creates a canonical route',
    'logical time advances on transition',
    'register state survives snapshot',
    'working memory survives snapshot',
    'route state survives warm rehydration',
    'unknown capability does not mutate continuation'
  ]
}, null, 2));
