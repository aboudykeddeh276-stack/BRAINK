#!/usr/bin/env node

const DEFAULT_ROOT = 'https://casepath.com.au/';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function decodeHtml(value) {
  return value
    .replaceAll('&amp;', '&')
    .replaceAll('&quot;', '"')
    .replaceAll('&#39;', "'")
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>');
}

function classify(url, rootOrigin) {
  if (url.origin !== rootOrigin) return 'EXTERNAL';
  if (url.pathname === '/' || url.pathname === '') return 'ROOT';
  if (/\.(?:js|mjs|css|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|map)$/i.test(url.pathname)) return 'ASSET';
  if (/\b(?:login|signin|signup|auth|account)\b/i.test(url.pathname)) return 'AUTH';
  if (/\b(?:admin|status|health|debug)\b/i.test(url.pathname)) return 'ADMIN_OR_STATUS';
  if (/\b(?:api|rpc|graphql|webhook)\b/i.test(url.pathname)) return 'SERVICE_ENDPOINT';
  return 'PUBLIC_ROUTE';
}

export function extractRouteGraph(html, root = DEFAULT_ROOT) {
  assert(typeof html === 'string' && html.length > 0, 'CASEPATH_HTML_REQUIRED');
  const rootUrl = new URL(root);
  const seen = new Map();
  const patterns = [
    /\bhref\s*=\s*["']([^"']+)["']/gi,
    /\bsrc\s*=\s*["']([^"']+)["']/gi,
    /\baction\s*=\s*["']([^"']+)["']/gi
  ];

  for (const pattern of patterns) {
    for (const match of html.matchAll(pattern)) {
      const raw = decodeHtml(match[1].trim());
      if (!raw || raw.startsWith('#') || raw.startsWith('javascript:') || raw.startsWith('mailto:') || raw.startsWith('tel:') || raw.startsWith('data:')) continue;
      let url;
      try { url = new URL(raw, rootUrl); } catch { continue; }
      const normalized = `${url.origin}${url.pathname}${url.search}`;
      if (!seen.has(normalized)) {
        seen.set(normalized, {
          url: normalized,
          origin: url.origin,
          path: url.pathname,
          query: url.search || null,
          class: classify(url, rootUrl.origin)
        });
      }
    }
  }

  const routes = [...seen.values()].sort((a, b) => a.url.localeCompare(b.url));
  const classes = routes.reduce((acc, route) => {
    acc[route.class] = (acc[route.class] ?? 0) + 1;
    return acc;
  }, {});

  return Object.freeze({
    schema: 'kex.braink.casepath-public-route-graph.v1',
    root: rootUrl.href,
    origin: rootUrl.origin,
    discovered_count: routes.length,
    classes,
    routes
  });
}

export async function discoverCasePathPublicRoutes({ root = DEFAULT_ROOT, fetchImpl = globalThis.fetch } = {}) {
  assert(typeof fetchImpl === 'function', 'FETCH_IMPLEMENTATION_REQUIRED');
  const response = await fetchImpl(root, {
    redirect: 'follow',
    headers: { accept: 'text/html,application/xhtml+xml' }
  });
  assert(response.ok, `CASEPATH_ROOT_HTTP_${response.status}`);
  const html = await response.text();
  const graph = extractRouteGraph(html, response.url || root);
  return Object.freeze({
    ...graph,
    observed_at: new Date().toISOString(),
    http_status: response.status,
    final_url: response.url || root,
    authority_role: 'PRIMARY_PUBLIC_ROUTE_DISCOVERY_SURFACE',
    google_ip_role: 'SECONDARY_NETWORK_CORROBORATION_ONLY'
  });
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  try {
    const graph = await discoverCasePathPublicRoutes();
    process.stdout.write(`${JSON.stringify(graph, null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`${JSON.stringify({
      schema: 'kex.braink.casepath-public-route-discovery.failure.v1',
      status: 'FAIL_CLOSED',
      error: String(error?.message ?? error)
    }, null, 2)}\n`);
    process.exitCode = 1;
  }
}
