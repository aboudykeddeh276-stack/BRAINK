#!/usr/bin/env node
import http from 'node:http';
import https from 'node:https';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { KeddehEdgeRuntime } from './keddeh-edge-runtime.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_SEED = path.join(HERE, 'keddeh-edge.seed.v1.json');

function parseArgs(argv) {
  const out = { seed: DEFAULT_SEED, bind: '127.0.0.1', port: 0, receiptDir: null, tlsCert: null, tlsKey: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--seed') out.seed = path.resolve(argv[++i]);
    else if (arg === '--bind') out.bind = argv[++i];
    else if (arg === '--port') out.port = Number(argv[++i]);
    else if (arg === '--receipt-dir') out.receiptDir = path.resolve(argv[++i]);
    else if (arg === '--tls-cert') out.tlsCert = path.resolve(argv[++i]);
    else if (arg === '--tls-key') out.tlsKey = path.resolve(argv[++i]);
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!Number.isInteger(out.port) || out.port < 0 || out.port > 65535) throw new Error('port must be 0..65535');
  if (Boolean(out.tlsCert) !== Boolean(out.tlsKey)) throw new Error('TLS cert and key must be supplied together');
  return out;
}

function writeReceipt(dir, name, payload) {
  if (!dir) return null;
  fs.mkdirSync(dir, { recursive: true });
  const target = path.join(dir, name);
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  return target;
}

function certificateMetadata(certPath) {
  if (!certPath) return null;
  const pem = fs.readFileSync(certPath, 'utf8');
  const x509 = new crypto.X509Certificate(pem);
  return { subject: x509.subject, issuer: x509.issuer, subject_alt_name: x509.subjectAltName, valid_from: x509.validFrom, valid_to: x509.validTo, fingerprint256: x509.fingerprint256, ca: x509.ca };
}

function makeHandler(runtime, requireTlsIdentity) {
  return (req, res) => {
    try {
      const socketSni = req.socket?.servername ?? null;
      const { resolution, response } = runtime.dispatch({ transport: requireTlsIdentity ? 'PUBLIC_TLS' : 'LOCAL_HTTP', requireSni: requireTlsIdentity, sni: socketSni, host: req.headers.host, method: req.method, path: req.url });
      const body = JSON.stringify(response.body);
      res.writeHead(response.status, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body), 'x-kex-edge': runtime.seed.edge_coordinate, 'x-kex-coordinate': resolution.coordinate });
      res.end(body);
    } catch (error) {
      const status = ['DOMAIN_BINDING_NOT_FOUND', 'SERVICE_ROUTE_NOT_FOUND'].includes(error.message) ? 404 : 400;
      const body = JSON.stringify({ state: 'EDGE_REJECTED', error: error.message, public_claim: false });
      res.writeHead(status, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) });
      res.end(body);
    }
  };
}

export async function startEdgeNode(options = {}) {
  const seed = options.seed ?? DEFAULT_SEED;
  const bind = options.bind ?? '127.0.0.1';
  const port = options.port ?? 0;
  const tlsCert = options.tlsCert ?? null;
  const tlsKey = options.tlsKey ?? null;
  const receiptDir = options.receiptDir ?? null;
  if (Boolean(tlsCert) !== Boolean(tlsKey)) throw new Error('TLS cert and key must be supplied together');

  const runtime = new KeddehEdgeRuntime(seed);
  const tlsEnabled = Boolean(tlsCert && tlsKey);
  const handler = makeHandler(runtime, tlsEnabled);
  const server = tlsEnabled ? https.createServer({ cert: fs.readFileSync(tlsCert), key: fs.readFileSync(tlsKey), minVersion: 'TLSv1.2' }, handler) : http.createServer(handler);
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, bind, resolve); });

  const address = server.address();
  const bootReceipt = {
    schema: 'kex.braink.keddeh-edge.node-boot-receipt.v1', edge: runtime.seed.edge_coordinate, lineage_root: runtime.seed.lineage_root,
    process_pid: process.pid, bind_address: address.address, bind_port: address.port, transport: tlsEnabled ? 'TLS_HTTPS' : 'HTTP',
    tls_certificate: certificateMetadata(tlsCert), runtime_snapshot: runtime.stateSnapshot(), state: 'EDGE_NODE_BOUND_OBSERVED_FROM_PROCESS', public_promotion: false,
    claim_boundary: 'This receipt proves the process bound its requested local/network interface. It is not outside-in proof of public reachability, DNS, certificate trust or public service availability.'
  };
  const bootReceiptPath = writeReceipt(receiptDir, 'edge-node-boot-receipt.json', bootReceipt);
  const stop = async (reason = 'REQUESTED') => {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    const stopReceipt = { schema: 'kex.braink.keddeh-edge.node-stop-receipt.v1', edge: runtime.seed.edge_coordinate, reason, state: 'EDGE_NODE_STOPPED', ledger_valid: runtime.proofPacket().ledger_valid, public_promotion: false };
    const stopReceiptPath = writeReceipt(receiptDir, 'edge-node-stop-receipt.json', stopReceipt);
    return { stopReceipt, stopReceiptPath };
  };
  return { runtime, server, address, bootReceipt, bootReceiptPath, stop };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = parseArgs(process.argv.slice(2));
    const node = await startEdgeNode(args);
    process.stdout.write(`${JSON.stringify(node.bootReceipt, null, 2)}\n`);
    const shutdown = async (signal) => { try { await node.stop(signal); process.exit(0); } catch (error) { process.stderr.write(`KEDDEH_EDGE_STOP_FAILED: ${error.message}\n`); process.exit(1); } };
    process.once('SIGINT', () => shutdown('SIGINT'));
    process.once('SIGTERM', () => shutdown('SIGTERM'));
  } catch (error) {
    process.stderr.write(`KEDDEH_EDGE_NODE_FAILED: ${error.message}\n`);
    process.exitCode = 1;
  }
}
