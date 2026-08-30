#!/usr/bin/env node
import net from 'node:net';

const SOURCES = Object.freeze({
  google_owned: 'https://www.gstatic.com/ipranges/goog.json',
  google_cloud_external: 'https://www.gstatic.com/ipranges/cloud.json'
});

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function normalizePrefix(entry, source) {
  const prefix = entry.ipv4Prefix ?? entry.ipv6Prefix;
  assert(typeof prefix === 'string' && prefix.includes('/'), `INVALID_GOOGLE_PREFIX:${source}`);
  const [address, lengthRaw] = prefix.split('/');
  const family = net.isIP(address);
  assert(family === 4 || family === 6, `INVALID_GOOGLE_IP:${prefix}`);
  const length = Number(lengthRaw);
  assert(Number.isInteger(length), `INVALID_GOOGLE_CIDR_LENGTH:${prefix}`);
  assert(length >= 0 && length <= (family === 4 ? 32 : 128), `GOOGLE_CIDR_LENGTH_OUT_OF_RANGE:${prefix}`);
  return Object.freeze({
    prefix,
    family: family === 4 ? 'IPv4' : 'IPv6',
    scope: entry.scope ?? null,
    service: entry.service ?? null,
    source
  });
}

function validateDocument(document, source) {
  assert(document && typeof document === 'object', `GOOGLE_IP_DOCUMENT_INVALID:${source}`);
  assert(typeof document.creationTime === 'string' && document.creationTime.length > 0, `GOOGLE_IP_CREATION_TIME_MISSING:${source}`);
  assert(Array.isArray(document.prefixes), `GOOGLE_IP_PREFIXES_MISSING:${source}`);
  return document;
}

export async function fetchGoogleIpAuthority({ fetchImpl = globalThis.fetch } = {}) {
  assert(typeof fetchImpl === 'function', 'FETCH_IMPLEMENTATION_REQUIRED');

  const records = {};
  for (const [source, url] of Object.entries(SOURCES)) {
    const response = await fetchImpl(url, {
      headers: { accept: 'application/json' },
      redirect: 'follow'
    });
    assert(response.ok, `GOOGLE_IP_SOURCE_HTTP_${response.status}:${source}`);
    const document = validateDocument(await response.json(), source);
    const prefixes = document.prefixes.map((entry) => normalizePrefix(entry, source));
    records[source] = Object.freeze({
      url,
      creationTime: document.creationTime,
      syncToken: document.syncToken ?? null,
      prefixCount: prefixes.length,
      prefixes: Object.freeze(prefixes)
    });
  }

  return Object.freeze({
    schema: 'kex.braink.google-ip-authority.v1',
    authority_class: 'GOOGLE_PUBLISHED_NETWORK_DATA',
    fetched_at: new Date().toISOString(),
    sources: SOURCES,
    google_owned: records.google_owned,
    google_cloud_external: records.google_cloud_external,
    interpretation: Object.freeze({
      google_owned: 'All Google-owned ranges published by goog.json.',
      google_cloud_external: 'Customer-usable global/regional external Google Cloud ranges published by cloud.json.',
      do_not_equate: 'Neither table alone proves that a specific request, hostname, product, tenant, or Google service originated from a listed address.',
      refresh_rule: 'Refresh from Google before authority-sensitive ingress decisions because ranges change frequently.'
    })
  });
}

export function summarizeGoogleIpAuthority(authority) {
  assert(authority?.schema === 'kex.braink.google-ip-authority.v1', 'GOOGLE_IP_AUTHORITY_SCHEMA_MISMATCH');
  return {
    schema: 'kex.braink.google-ip-authority.summary.v1',
    fetched_at: authority.fetched_at,
    google_owned_creation_time: authority.google_owned.creationTime,
    google_owned_prefixes: authority.google_owned.prefixCount,
    google_cloud_creation_time: authority.google_cloud_external.creationTime,
    google_cloud_external_prefixes: authority.google_cloud_external.prefixCount,
    refresh_rule: authority.interpretation.refresh_rule
  };
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  try {
    const authority = await fetchGoogleIpAuthority();
    process.stdout.write(`${JSON.stringify(summarizeGoogleIpAuthority(authority), null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`${JSON.stringify({
      schema: 'kex.braink.google-ip-authority.failure.v1',
      status: 'FAIL_CLOSED',
      error: String(error?.message ?? error)
    }, null, 2)}\n`);
    process.exitCode = 1;
  }
}
