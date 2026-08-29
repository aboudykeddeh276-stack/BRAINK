export type DependencyCriticality =
  | 'CORE_MANDATORY'
  | 'CORE_DEGRADED'
  | 'OPTIONAL'
  | 'EXTERNAL_GATE'
  | 'REPLACEABLE'
  | 'DEFERRED_COMMIT';

export type FailureState =
  | 'ACTIVE'
  | 'DEGRADED'
  | 'DEFERRED'
  | 'RECOVERING'
  | 'REINTEGRATED'
  | 'BOUNDED_STOP';

export type DeferredWorkState = 'QUEUED' | 'REPLAYING' | 'COMPLETED' | 'FAILED';

export interface DeferredWorkItem<TPayload = unknown> {
  workId: string;
  payload: TPayload;
  state: DeferredWorkState;
  attempts: number;
  lastError?: string;
  createdAt: string;
  updatedAt: string;
}

export interface DependencyFailureRecord<TPayload = unknown> {
  failureId: string;
  blockedCapability: string;
  blockedDomain: string;
  dependencyId: string;
  criticality: DependencyCriticality;
  rootCause: string;
  state: FailureState;
  impactRadius: string[];
  unaffectedDomains: string[];
  continuationMode: string;
  fallbackAdapter?: string;
  recoveryConditions: string[];
  evidence: Record<string, unknown>;
  deferredWork: DeferredWorkItem<TPayload>[];
  createdAt: string;
  updatedAt: string;
  reconciledAt?: string;
  lineage: {
    source: string;
    priorFailureId?: string;
    activeWordAddress?: string;
    expressionAddress?: string;
    receiptIds: string[];
  };
}

export interface ReconciliationContext {
  observer: string;
  observedAt: string;
  dependencyHealthy: boolean;
  evidence: Record<string, unknown>;
}

export interface ReconciliationReceipt {
  receiptId: string;
  failureId: string;
  state: FailureState;
  replayed: number;
  remaining: number;
  globalStop: false;
  observedAt: string;
  observer: string;
  errors: Array<{ workId: string; error: string }>;
}

export interface FailureLedgerOptions {
  databaseName?: string;
  databaseVersion?: number;
  durability?: IDBTransactionDurability;
  clock?: () => Date;
}

export type DeferredWorkExecutor<TPayload = unknown> = (
  item: DeferredWorkItem<TPayload>,
  failure: DependencyFailureRecord<TPayload>,
) => Promise<void>;

const DB_NAME = 'keddeh-sovereign-failure-ledger';
const DB_VERSION = 1;
const FAILURE_STORE = 'failures';
const RECEIPT_STORE = 'receipts';
const META_STORE = 'metadata';

function requestToPromise<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('IndexedDB request failed'));
  });
}

function transactionToPromise(transaction: IDBTransaction): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error ?? new Error('IndexedDB transaction aborted'));
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'));
  });
}

async function sha256(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

export class FailureLedger<TPayload = unknown> {
  private readonly databaseName: string;
  private readonly databaseVersion: number;
  private readonly durability: IDBTransactionDurability;
  private readonly clock: () => Date;
  private databasePromise?: Promise<IDBDatabase>;

  constructor(options: FailureLedgerOptions = {}) {
    this.databaseName = options.databaseName ?? DB_NAME;
    this.databaseVersion = options.databaseVersion ?? DB_VERSION;
    this.durability = options.durability ?? 'strict';
    this.clock = options.clock ?? (() => new Date());
  }

  async open(): Promise<void> {
    await this.database();
  }

  async close(): Promise<void> {
    if (!this.databasePromise) return;
    const database = await this.databasePromise;
    database.close();
    this.databasePromise = undefined;
  }

  async record(
    input: Omit<DependencyFailureRecord<TPayload>, 'createdAt' | 'updatedAt'> &
      Partial<Pick<DependencyFailureRecord<TPayload>, 'createdAt' | 'updatedAt'>>,
  ): Promise<DependencyFailureRecord<TPayload>> {
    const now = this.clock().toISOString();
    const record: DependencyFailureRecord<TPayload> = {
      ...clone(input),
      createdAt: input.createdAt ?? now,
      updatedAt: now,
      deferredWork: (input.deferredWork ?? []).map((item) => ({
        ...clone(item),
        attempts: item.attempts ?? 0,
        state: item.state ?? 'QUEUED',
        createdAt: item.createdAt ?? now,
        updatedAt: now,
      })),
      lineage: {
        ...clone(input.lineage),
        receiptIds: [...(input.lineage.receiptIds ?? [])],
      },
    };

    const database = await this.database();
    const transaction = database.transaction([FAILURE_STORE], 'readwrite', {
      durability: this.durability,
    });
    transaction.objectStore(FAILURE_STORE).put(record);
    await transactionToPromise(transaction);
    return clone(record);
  }

  async get(failureId: string): Promise<DependencyFailureRecord<TPayload> | undefined> {
    const database = await this.database();
    const transaction = database.transaction([FAILURE_STORE], 'readonly');
    const result = await requestToPromise(
      transaction.objectStore(FAILURE_STORE).get(failureId) as IDBRequest<DependencyFailureRecord<TPayload> | undefined>,
    );
    await transactionToPromise(transaction);
    return result ? clone(result) : undefined;
  }

  async list(filters: {
    state?: FailureState;
    criticality?: DependencyCriticality;
    dependencyId?: string;
  } = {}): Promise<Array<DependencyFailureRecord<TPayload>>> {
    const database = await this.database();
    const transaction = database.transaction([FAILURE_STORE], 'readonly');
    const store = transaction.objectStore(FAILURE_STORE);
    const records = await requestToPromise(store.getAll() as IDBRequest<Array<DependencyFailureRecord<TPayload>>>);
    await transactionToPromise(transaction);
    return records
      .filter((record) => !filters.state || record.state === filters.state)
      .filter((record) => !filters.criticality || record.criticality === filters.criticality)
      .filter((record) => !filters.dependencyId || record.dependencyId === filters.dependencyId)
      .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
      .map(clone);
  }

  async enqueueDeferredWork(failureId: string, work: Omit<DeferredWorkItem<TPayload>, 'createdAt' | 'updatedAt'>): Promise<void> {
    const failure = await this.requireFailure(failureId);
    if (failure.deferredWork.some((item) => item.workId === work.workId)) return;
    const now = this.clock().toISOString();
    failure.deferredWork.push({
      ...clone(work),
      state: work.state ?? 'QUEUED',
      attempts: work.attempts ?? 0,
      createdAt: now,
      updatedAt: now,
    });
    failure.state = 'DEFERRED';
    failure.updatedAt = now;
    await this.record(failure);
  }

  async reconcile(
    failureId: string,
    context: ReconciliationContext,
    executor: DeferredWorkExecutor<TPayload>,
  ): Promise<ReconciliationReceipt> {
    const failure = await this.requireFailure(failureId);
    const errors: Array<{ workId: string; error: string }> = [];
    let replayed = 0;

    if (!context.dependencyHealthy) {
      failure.state = failure.criticality === 'CORE_MANDATORY' ? 'BOUNDED_STOP' : 'DEFERRED';
      failure.evidence = { ...failure.evidence, latestReconciliation: clone(context) };
      failure.updatedAt = this.clock().toISOString();
      await this.record(failure);
      return this.persistReceipt(failure, context, replayed, errors);
    }

    failure.state = 'RECOVERING';
    failure.updatedAt = this.clock().toISOString();
    await this.record(failure);

    for (const item of failure.deferredWork) {
      if (item.state === 'COMPLETED') continue;
      item.state = 'REPLAYING';
      item.attempts += 1;
      item.updatedAt = this.clock().toISOString();
      await this.record(failure);
      try {
        await executor(clone(item), clone(failure));
        item.state = 'COMPLETED';
        item.lastError = undefined;
        replayed += 1;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        item.state = 'FAILED';
        item.lastError = message;
        errors.push({ workId: item.workId, error: message });
      }
      item.updatedAt = this.clock().toISOString();
      await this.record(failure);
    }

    const remaining = failure.deferredWork.filter((item) => item.state !== 'COMPLETED').length;
    failure.state = remaining === 0 ? 'REINTEGRATED' : 'DEFERRED';
    failure.reconciledAt = remaining === 0 ? this.clock().toISOString() : undefined;
    failure.evidence = {
      ...failure.evidence,
      latestReconciliation: clone(context),
    };
    failure.updatedAt = this.clock().toISOString();
    await this.record(failure);
    return this.persistReceipt(failure, context, replayed, errors);
  }

  async recoverOnStartup(
    healthResolver: (failure: DependencyFailureRecord<TPayload>) => Promise<ReconciliationContext>,
    executor: DeferredWorkExecutor<TPayload>,
  ): Promise<ReconciliationReceipt[]> {
    const recoverable = await this.list();
    const receipts: ReconciliationReceipt[] = [];
    for (const failure of recoverable) {
      if (!['ACTIVE', 'DEGRADED', 'DEFERRED', 'RECOVERING', 'BOUNDED_STOP'].includes(failure.state)) continue;
      const context = await healthResolver(clone(failure));
      receipts.push(await this.reconcile(failure.failureId, context, executor));
    }
    return receipts;
  }

  async receipt(receiptId: string): Promise<ReconciliationReceipt | undefined> {
    const database = await this.database();
    const transaction = database.transaction([RECEIPT_STORE], 'readonly');
    const value = await requestToPromise(
      transaction.objectStore(RECEIPT_STORE).get(receiptId) as IDBRequest<ReconciliationReceipt | undefined>,
    );
    await transactionToPromise(transaction);
    return value ? clone(value) : undefined;
  }

  private async persistReceipt(
    failure: DependencyFailureRecord<TPayload>,
    context: ReconciliationContext,
    replayed: number,
    errors: Array<{ workId: string; error: string }>,
  ): Promise<ReconciliationReceipt> {
    const remaining = failure.deferredWork.filter((item) => item.state !== 'COMPLETED').length;
    const seed = {
      failureId: failure.failureId,
      state: failure.state,
      replayed,
      remaining,
      observedAt: context.observedAt,
      observer: context.observer,
      errors,
    };
    const receipt: ReconciliationReceipt = {
      receiptId: `receipt://failure-ledger/${await sha256(seed)}`,
      failureId: failure.failureId,
      state: failure.state,
      replayed,
      remaining,
      globalStop: false,
      observedAt: context.observedAt,
      observer: context.observer,
      errors,
    };

    failure.lineage.receiptIds.push(receipt.receiptId);
    await this.record(failure);

    const database = await this.database();
    const transaction = database.transaction([RECEIPT_STORE], 'readwrite', {
      durability: this.durability,
    });
    transaction.objectStore(RECEIPT_STORE).put(receipt);
    await transactionToPromise(transaction);
    return clone(receipt);
  }

  private async requireFailure(failureId: string): Promise<DependencyFailureRecord<TPayload>> {
    const failure = await this.get(failureId);
    if (!failure) throw new Error(`Unknown failure record: ${failureId}`);
    return failure;
  }

  private database(): Promise<IDBDatabase> {
    if (this.databasePromise) return this.databasePromise;
    this.databasePromise = new Promise<IDBDatabase>((resolve, reject) => {
      if (!globalThis.indexedDB) {
        reject(new Error('IndexedDB is unavailable in this execution environment'));
        return;
      }
      const request = globalThis.indexedDB.open(this.databaseName, this.databaseVersion);
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains(FAILURE_STORE)) {
          const failures = database.createObjectStore(FAILURE_STORE, { keyPath: 'failureId' });
          failures.createIndex('state', 'state', { unique: false });
          failures.createIndex('criticality', 'criticality', { unique: false });
          failures.createIndex('dependencyId', 'dependencyId', { unique: false });
          failures.createIndex('updatedAt', 'updatedAt', { unique: false });
        }
        if (!database.objectStoreNames.contains(RECEIPT_STORE)) {
          database.createObjectStore(RECEIPT_STORE, { keyPath: 'receiptId' });
        }
        if (!database.objectStoreNames.contains(META_STORE)) {
          database.createObjectStore(META_STORE, { keyPath: 'key' });
        }
      };
      request.onsuccess = () => {
        const database = request.result;
        database.onversionchange = () => database.close();
        resolve(database);
      };
      request.onerror = () => reject(request.error ?? new Error('Failed to open FailureLedger IndexedDB'));
      request.onblocked = () => reject(new Error('FailureLedger database upgrade is blocked by another tab'));
    });
    return this.databasePromise;
  }
}
