#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const sha256 = (value) => crypto.createHash('sha256').update(value).digest('hex');

function parseArgs(argv) {
  const out = { write: false, root: process.cwd() };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--write') out.write = true;
    else if (arg === '--action') out.action = argv[++i];
    else if (arg === '--root') out.root = argv[++i];
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!out.action) throw new Error('Required: --action <packet.json>');
  return out;
}

function safePath(root, relativePath) {
  if (typeof relativePath !== 'string' || relativePath.trim() === '') {
    throw new Error('Path must be a non-empty relative string');
  }
  if (path.isAbsolute(relativePath)) throw new Error(`Absolute path forbidden: ${relativePath}`);
  const resolvedRoot = path.resolve(root);
  const resolved = path.resolve(resolvedRoot, relativePath);
  if (resolved !== resolvedRoot && !resolved.startsWith(`${resolvedRoot}${path.sep}`)) {
    throw new Error(`Path escapes repository root: ${relativePath}`);
  }
  return resolved;
}

function countOccurrences(haystack, needle) {
  if (needle === '') throw new Error('Empty match strings are forbidden');
  let count = 0;
  let offset = 0;
  while (true) {
    const index = haystack.indexOf(needle, offset);
    if (index < 0) return count;
    count += 1;
    offset = index + needle.length;
  }
}

function replaceAllExact(source, find, replacement) {
  return source.split(find).join(replacement);
}

function lineNumberAt(source, offset) {
  return source.slice(0, offset).split('\n').length;
}

function buildElementIndex(source) {
  const entries = [];
  const seen = new Set();
  const tagPattern = /<([A-Za-z][\w:-]*)([^>]*?)>/g;
  let match;
  while ((match = tagPattern.exec(source)) !== null) {
    const tag = match[1].toLowerCase();
    const attrs = match[2];
    const ids = [];
    const idMatch = attrs.match(/\bid\s*=\s*(["'])(.*?)\1/i);
    if (idMatch) ids.push(['id', idMatch[2]]);
    const elementMatch = attrs.match(/\bdata-site-element\s*=\s*(["'])(.*?)\1/i);
    if (elementMatch) ids.push(['data-site-element', elementMatch[2]]);
    for (const [kind, value] of ids) {
      const key = `${kind}:${value}`;
      if (seen.has(key)) continue;
      seen.add(key);
      entries.push({ key, kind, value, tag, line: lineNumberAt(source, match.index) });
    }
  }

  const markerPattern = /<!--\s*SITE:ELEMENT:([A-Za-z0-9_.:-]+):(START|END)\s*-->/g;
  while ((match = markerPattern.exec(source)) !== null) {
    const key = `marker:${match[1]}:${match[2]}`;
    if (!seen.has(key)) {
      seen.add(key);
      entries.push({ key, kind: 'marker', value: `${match[1]}:${match[2]}`, tag: 'comment', line: lineNumberAt(source, match.index) });
    }
  }

  entries.sort((a, b) => a.line - b.line || a.key.localeCompare(b.key));
  return {
    schema: 'braink.site.element-index.v1',
    count: entries.length,
    entries,
    sha256: sha256(JSON.stringify(entries))
  };
}

function applyOperation(source, op, index) {
  if (!op || typeof op !== 'object') throw new Error(`Operation ${index} must be an object`);
  const type = op.type;

  if (type === 'assert_contains' || type === 'assert_not_contains') {
    const found = source.includes(op.text);
    const pass = type === 'assert_contains' ? found : !found;
    if (!pass) throw new Error(`Operation ${index} ${type} failed`);
    return { source, result: { index, type, matched: found ? 1 : 0, changed: false } };
  }

  if (type === 'replace_exact') {
    const actual = countOccurrences(source, op.find);
    const expected = op.expected_count ?? 1;
    if (actual !== expected) throw new Error(`Operation ${index} replace_exact expected ${expected} matches, found ${actual}`);
    const next = replaceAllExact(source, op.find, op.replacement ?? '');
    return { source: next, result: { index, type, matched: actual, changed: next !== source } };
  }

  if (type === 'insert_before_exact' || type === 'insert_after_exact') {
    const actual = countOccurrences(source, op.anchor);
    const expected = op.expected_count ?? 1;
    if (actual !== expected) throw new Error(`Operation ${index} ${type} expected ${expected} anchors, found ${actual}`);
    const replacement = type === 'insert_before_exact'
      ? `${op.content ?? ''}${op.anchor}`
      : `${op.anchor}${op.content ?? ''}`;
    const next = replaceAllExact(source, op.anchor, replacement);
    return { source: next, result: { index, type, matched: actual, changed: next !== source } };
  }

  if (type === 'replace_marker') {
    const start = `<!-- SITE:ELEMENT:${op.marker}:START -->`;
    const end = `<!-- SITE:ELEMENT:${op.marker}:END -->`;
    const startCount = countOccurrences(source, start);
    const endCount = countOccurrences(source, end);
    if (startCount !== 1 || endCount !== 1) {
      throw new Error(`Operation ${index} replace_marker requires exactly one START and END marker for ${op.marker}`);
    }
    const startAt = source.indexOf(start) + start.length;
    const endAt = source.indexOf(end, startAt);
    if (endAt < startAt) throw new Error(`Operation ${index} marker order invalid for ${op.marker}`);
    const next = `${source.slice(0, startAt)}${op.content ?? ''}${source.slice(endAt)}`;
    return { source: next, result: { index, type, marker: op.marker, matched: 1, changed: next !== source } };
  }

  if (type === 'set_css_var') {
    if (!/^--[A-Za-z0-9_-]+$/.test(op.name ?? '')) throw new Error(`Operation ${index} invalid CSS variable name`);
    const escaped = op.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp(`(${escaped}\\s*:\\s*)([^;]+)(;)`, 'g');
    const matches = [...source.matchAll(pattern)];
    const expected = op.expected_count ?? 1;
    if (matches.length !== expected) throw new Error(`Operation ${index} set_css_var expected ${expected} matches, found ${matches.length}`);
    const next = source.replace(pattern, `$1${op.value}$3`);
    return { source: next, result: { index, type, name: op.name, matched: matches.length, changed: next !== source } };
  }

  throw new Error(`Operation ${index} unsupported type: ${type}`);
}

function validatePacket(packet) {
  if (!packet || typeof packet !== 'object') throw new Error('Action packet must be a JSON object');
  if (packet.schema !== 'braink.site.action.v1') throw new Error(`Unsupported schema: ${packet.schema}`);
  for (const field of ['action_id', 'site', 'target', 'intent']) {
    if (typeof packet[field] !== 'string' || packet[field].trim() === '') throw new Error(`Missing required field: ${field}`);
  }
  if (!Array.isArray(packet.operations) || packet.operations.length === 0) throw new Error('operations must be a non-empty array');
  if (packet.invariants != null && !Array.isArray(packet.invariants)) throw new Error('invariants must be an array when present');
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const root = path.resolve(args.root);
  const actionPath = safePath(root, args.action);
  const packetText = fs.readFileSync(actionPath, 'utf8');
  const packet = JSON.parse(packetText);
  validatePacket(packet);

  const targetPath = safePath(root, packet.target);
  const before = fs.readFileSync(targetPath, 'utf8');
  const sourceHashBefore = sha256(before);
  const actionHash = sha256(packetText);
  const elementIndexBefore = buildElementIndex(before);

  let candidate = before;
  const results = [];
  for (let i = 0; i < packet.operations.length; i += 1) {
    const applied = applyOperation(candidate, packet.operations[i], i);
    candidate = applied.source;
    results.push(applied.result);
  }

  const sourceHashAfter = sha256(candidate);
  const elementIndexAfter = buildElementIndex(candidate);
  const runId = sha256(`${packet.action_id}\n${actionHash}\n${sourceHashBefore}\n${sourceHashAfter}`);
  const receipt = {
    schema: 'braink.site.action.receipt.v1',
    run_id: runId,
    action_id: packet.action_id,
    action_sha256: actionHash,
    site: packet.site,
    target: packet.target,
    intent: packet.intent,
    invariants: packet.invariants ?? [],
    source_sha256_before: sourceHashBefore,
    source_sha256_after: sourceHashAfter,
    changed: before !== candidate,
    operations: results,
    element_index_before_sha256: elementIndexBefore.sha256,
    element_index_after_sha256: elementIndexAfter.sha256,
    state: args.write ? 'SOURCE_APPLIED' : 'PREFLIGHT_PASS'
  };

  if (args.write) {
    fs.writeFileSync(targetPath, candidate, 'utf8');

    const receiptRel = packet.receipt ?? `site-actions/receipts/${packet.action_id}.json`;
    const receiptPath = safePath(root, receiptRel);
    fs.mkdirSync(path.dirname(receiptPath), { recursive: true });
    fs.writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');

    const indexRel = packet.element_index ?? `site-actions/indexes/${packet.site}.json`;
    const indexPath = safePath(root, indexRel);
    fs.mkdirSync(path.dirname(indexPath), { recursive: true });
    fs.writeFileSync(indexPath, `${JSON.stringify(elementIndexAfter, null, 2)}\n`, 'utf8');
  }

  process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`SITE_ACTION_FAILED: ${error.message}\n`);
  process.exitCode = 1;
}
