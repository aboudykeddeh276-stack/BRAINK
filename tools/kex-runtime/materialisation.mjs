export class MaterialisationRegistry {
  constructor({ ledger }) {
    this.ledger = ledger;
    this.adapters = new Map();
    this.requests = new Map();
    this.counter = 0;
  }

  registerAdapter(adapter) {
    for (const field of ['id', 'type', 'externalBoundary']) {
      if (!adapter?.[field]) throw new Error(`Adapter missing ${field}`);
    }
    if (adapter.externalBoundary !== true) throw new Error('Materialisation adapter must be external boundary');
    this.adapters.set(adapter.id, Object.freeze({ ...adapter, in_lineage: false }));
    this.ledger.append('REGISTER_EXTERNAL_ADAPTER', {
      adapter_id: adapter.id,
      adapter_type: adapter.type,
      in_lineage: false
    });
  }

  request({ lineageCoordinate, machineCoordinate, adapterId, payload }) {
    const adapter = this.adapters.get(adapterId);
    if (!adapter) throw new Error(`Unknown adapter ${adapterId}`);
    const requestId = `KEX://MATERIALISATION-REQUEST/${String(++this.counter).padStart(8, '0')}`;
    const request = Object.freeze({
      request_id: requestId,
      lineage_coordinate: lineageCoordinate,
      machine_coordinate: machineCoordinate,
      adapter_id: adapterId,
      adapter_type: adapter.type,
      external_boundary: true,
      in_lineage: false,
      payload,
      state: 'PENDING_EXTERNAL_ACTUATION'
    });
    this.requests.set(requestId, request);
    this.ledger.append('REQUEST_EXTERNAL_MATERIALISATION', request);
    return request;
  }

  acceptReceipt(requestId, receipt) {
    const request = this.requests.get(requestId);
    if (!request) throw new Error(`Unknown materialisation request ${requestId}`);
    if (!receipt || receipt.scope !== 'EXTERNAL') throw new Error('External actuation receipt must have scope EXTERNAL');
    const completed = Object.freeze({
      ...request,
      state: 'EXTERNAL_ACTUATION_RECEIPTED',
      receipt: Object.freeze({ ...receipt })
    });
    this.requests.set(requestId, completed);
    this.ledger.append('ACCEPT_EXTERNAL_MATERIALISATION_RECEIPT', {
      request_id: requestId,
      observer: receipt.observer ?? 'UNSPECIFIED',
      receipt: receipt.receipt ?? null
    });
    return completed;
  }
}

export const DEFAULT_ADAPTERS = Object.freeze([
  Object.freeze({ id: 'QEMU_SYSTEM', type: 'QEMU_SYSTEM_EMULATION', externalBoundary: true }),
  Object.freeze({ id: 'KVM', type: 'LINUX_KVM_ACCELERATION', externalBoundary: true }),
  Object.freeze({ id: 'HVF', type: 'MACOS_HYPERVISOR_FRAMEWORK', externalBoundary: true }),
  Object.freeze({ id: 'CLOUD', type: 'CLOUD_COMPUTE_CARRIER', externalBoundary: true }),
  Object.freeze({ id: 'BARE_METAL', type: 'PHYSICAL_BARE_METAL_CARRIER', externalBoundary: true }),
  Object.freeze({ id: 'BIND9', type: 'AUTHORITATIVE_DNS_PROJECTION', externalBoundary: true }),
  Object.freeze({ id: 'FRR', type: 'BGP_ROUTING_PROJECTION', externalBoundary: true }),
  Object.freeze({ id: 'API_EDGE', type: 'PUBLIC_API_INGRESS_PROJECTION', externalBoundary: true })
]);
