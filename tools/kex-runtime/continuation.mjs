#!/usr/bin/env node
import crypto from 'node:crypto';

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((k) => [k, stable(value[k])]));
  }
  return value;
}

function digest(value) {
  return crypto.createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
}

export const CONTINUATION_SCHEMA = 'braink.continuation.v1';

/**
 * Canonical execution continuation. A continuation is durable computational
 * state, not a transcript and not a UI session. Projection layers may carry a
 * reference to it but never become its source of truth.
 */
export class ContinuationFrame {
  constructor({
    id,
    taskId,
    goal,
    observer = {},
    logicalTime = 0,
    workingMemory = {},
    registers = [],
    routeStack = [],
    returnStack = [],
    proofCursor = null,
    authority = {},
    evidence = [],
    obligations = [],
    failureContext = [],
    projection = null,
    stateRoot = null,
  }) {
    if (!id || !taskId) throw new TypeError('continuation id and task id are required');
    if (!Number.isSafeInteger(logicalTime) || logicalTime < 0) throw new TypeError('logicalTime must be a non-negative safe integer');
    this.schema = CONTINUATION_SCHEMA;
    this.id = id;
    this.taskId = taskId;
    this.goal = goal;
    this.observer = structuredClone(observer);
    this.logicalTime = logicalTime;
    this.workingMemory = structuredClone(workingMemory);
    this.registers = Object.freeze([...registers]);
    this.routeStack = Object.freeze([...routeStack]);
    this.returnStack = Object.freeze([...returnStack]);
    this.proofCursor = proofCursor;
    this.authority = structuredClone(authority);
    this.evidence = Object.freeze([...evidence]);
    this.obligations = Object.freeze([...obligations]);
    this.failureContext = Object.freeze([...failureContext]);
    this.projection = projection;
    this.stateRoot = stateRoot ?? digest({ id, taskId, goal, observer, logicalTime, workingMemory, registers, routeStack, returnStack, proofCursor, authority, evidence, obligations, failureContext, projection });
    Object.freeze(this);
  }

  transition({ route, result, evidence = null, obligationDelta = [], failure = null, projection = this.projection }) {
    if (!route) throw new TypeError('route is required');
    const nextMemory = { ...this.workingMemory, last_result: result };
    const nextEvidence = evidence ? [...this.evidence, evidence] : this.evidence;
    const nextObligations = [...this.obligations, ...obligationDelta].filter((x) => x && x.status !== 'RESOLVED');
    const nextFailures = failure ? [...this.failureContext, failure] : this.failureContext;
    return new ContinuationFrame({
      id: this.id,
      taskId: this.taskId,
      goal: this.goal,
      observer: this.observer,
      logicalTime: this.logicalTime + 1,
      workingMemory: nextMemory,
      registers: this.registers,
      routeStack: [...this.routeStack, route],
      returnStack: [...this.returnStack, this.routeStack.at(-1) ?? null],
      proofCursor: evidence?.proof_cursor ?? this.proofCursor,
      authority: this.authority,
      evidence: nextEvidence,
      obligations: nextObligations,
      failureContext: nextFailures,
      projection,
    });
  }

  traverse(target) {
    if (!target) throw new TypeError('target is required');
    return new ContinuationFrame({
      id: this.id,
      taskId: this.taskId,
      goal: this.goal,
      observer: this.observer,
      logicalTime: this.logicalTime + 1,
      workingMemory: this.workingMemory,
      registers: this.registers,
      routeStack: [...this.routeStack, target],
      returnStack: [...this.returnStack, this.routeStack.at(-1) ?? null],
      proofCursor: this.proofCursor,
      authority: this.authority,
      evidence: this.evidence,
      obligations: this.obligations,
      failureContext: this.failureContext,
      projection: this.projection,
    });
  }

  returnToParent() {
    if (!this.returnStack.length) return this;
    const nextRoute = this.returnStack.at(-1);
    return new ContinuationFrame({
      id: this.id,
      taskId: this.taskId,
      goal: this.goal,
      observer: this.observer,
      logicalTime: this.logicalTime + 1,
      workingMemory: this.workingMemory,
      registers: this.registers,
      routeStack: nextRoute ? [...this.routeStack.slice(0, -1)] : this.routeStack,
      returnStack: this.returnStack.slice(0, -1),
      proofCursor: this.proofCursor,
      authority: this.authority,
      evidence: this.evidence,
      obligations: this.obligations,
      failureContext: this.failureContext,
      projection: this.projection,
    });
  }

  snapshot() {
    return JSON.parse(JSON.stringify(this));
  }

  static rehydrate(snapshot) {
    if (!snapshot || snapshot.schema !== CONTINUATION_SCHEMA) throw new Error('Invalid continuation schema');
    const frame = new ContinuationFrame(snapshot);
    if (frame.stateRoot !== snapshot.stateRoot) throw new Error('Continuation state-root mismatch');
    return frame;
  }
}
