#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { ContinuationFrame } from './continuation.mjs';

export const RESOLUTION_ORDER = Object.freeze([
  'INSPECT_EXISTING',
  'VERIFY_FRESHNESS',
  'REUSE',
  'ADAPT',
  'BRIDGE',
  'DERIVE',
  'UNKNOWN',
]);

function readJSON(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function candidateCapabilities(registry) {
  if (Array.isArray(registry?.canonical_capabilities)) {
    return registry.canonical_capabilities.map((value) => ({ ...value, capability_id: value.id }));
  }
  const result = [];
  for (const [domain, value] of Object.entries(registry?.capabilities ?? registry?.substrates ?? {})) {
    if (value && typeof value === 'object') result.push({ domain, ...value, capability_id: value.capability_id ?? value.id });
  }
  return result;
}

/**
 * Resolves an intent against the authoritative capability topology before any
 * new architecture is derived. It returns a route description; it does not
 * execute external actuation.
 */
export class CapabilityResolver {
  constructor({ registryPath, currentResolutionPath = null } = {}) {
    if (!registryPath) throw new TypeError('registryPath is required');
    this.registryPath = registryPath;
    this.currentResolutionPath = currentResolutionPath;
  }

  discover() {
    const registry = readJSON(this.registryPath);
    const current = this.currentResolutionPath && fs.existsSync(this.currentResolutionPath)
      ? readJSON(this.currentResolutionPath)
      : null;
    return Object.freeze({
      registry,
      current,
      capabilities: Object.freeze(candidateCapabilities(registry)),
    });
  }

  resolve({ intent, continuation, requiredCapability = null, adapter = null } = {}) {
    if (!(continuation instanceof ContinuationFrame)) throw new TypeError('continuation is required');
    if (!intent || typeof intent !== 'string') throw new TypeError('intent is required');

    const topology = this.discover();
    const needle = (requiredCapability ?? intent).toLowerCase();
    const exact = topology.capabilities.find((c) => JSON.stringify(c).toLowerCase().includes(needle));

    if (exact) {
      const capabilityId = exact.capability_id ?? exact.id ?? exact.domain;
      return Object.freeze({
        status: 'RESOLVED',
        method: 'REUSE',
        capability: exact,
        adapter,
        route: `capability://${capabilityId}`,
        next: continuation.traverse(`capability://${capabilityId}`),
      });
    }

    if (adapter) {
      return Object.freeze({
        status: 'RESOLVED',
        method: 'ADAPT',
        capability: null,
        adapter,
        route: `adapter://${adapter}`,
        next: continuation.traverse(`adapter://${adapter}`),
      });
    }

    return Object.freeze({
      status: 'UNKNOWN',
      method: 'UNKNOWN',
      capability: null,
      adapter: null,
      route: null,
      next: continuation,
    });
  }
}

export function registryPathFromRuntime(runtimeDirectory) {
  return path.resolve(runtimeDirectory, '../kex-capability-discovery/infrastructure-capability-registry.json');
}
