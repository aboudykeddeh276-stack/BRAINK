export class BRAINKAdapter {
  constructor(options = {}) {
    this.endpoint = options.endpoint || '/braink/dispatch';
    this.site = options.site || (typeof location !== 'undefined' ? location.host : 'unknown');
    this.agent = options.agent || 'braink-web-adapter';
    this.timeoutMs = options.timeoutMs || 30000;
    this.headers = options.headers || {};
    this.capabilities = new Map();
    this.started = false;
  }

  async start() {
    if (this.started) return this;
    this.started = true;
    this._emit('braink:adapter:ready', {
      site: this.site,
      agent: this.agent,
      endpoint: this.endpoint
    });
    return this;
  }

  registerCapability(name, handler) {
    if (!name || typeof handler !== 'function') {
      throw new TypeError('registerCapability(name, handler) requires a name and function');
    }
    this.capabilities.set(name, handler);
    return () => this.capabilities.delete(name);
  }

  async dispatch(intent, payload = {}, options = {}) {
    if (!this.started) await this.start();
    if (!intent || typeof intent !== 'string') {
      throw new TypeError('dispatch(intent, payload) requires a string intent');
    }

    const correlationId = options.correlationId || crypto.randomUUID();
    const envelope = {
      protocol: 'braink.adapter.v1',
      kind: 'intent',
      correlation_id: correlationId,
      site: this.site,
      agent: this.agent,
      intent,
      payload,
      requested_capabilities: options.capabilities || [],
      proof_required: options.proofRequired !== false,
      issued_at: new Date().toISOString()
    };

    this._emit('braink:dispatch:start', envelope);

    try {
      const result = this.capabilities.has(intent)
        ? await this._dispatchLocal(intent, envelope)
        : await this._dispatchRemote(envelope, options);

      this._validateResult(result, correlationId);
      this._emit('braink:dispatch:complete', result);
      return result;
    } catch (error) {
      const failure = {
        protocol: 'braink.adapter.v1',
        kind: 'error',
        correlation_id: correlationId,
        intent,
        error: error instanceof Error ? error.message : String(error),
        observed_at: new Date().toISOString()
      };
      this._emit('braink:dispatch:error', failure);
      throw error;
    }
  }

  async _dispatchLocal(intent, envelope) {
    const handler = this.capabilities.get(intent);
    const output = await handler(envelope.payload, envelope);
    return {
      protocol: 'braink.adapter.v1',
      kind: 'result',
      correlation_id: envelope.correlation_id,
      route: `local:${intent}`,
      status: 'completed',
      output,
      proof: {
        source: 'resident-web-capability',
        observed: true
      }
    };
  }

  async _dispatchRemote(envelope, options) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), options.timeoutMs || this.timeoutMs);

    try {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          ...this.headers,
          ...(options.headers || {})
        },
        credentials: options.credentials || 'same-origin',
        signal: controller.signal,
        body: JSON.stringify(envelope)
      });

      const text = await response.text();
      let body;
      try {
        body = text ? JSON.parse(text) : {};
      } catch {
        throw new Error(`BRAINK gateway returned non-JSON response (${response.status})`);
      }

      if (!response.ok) {
        throw new Error(body.error || `BRAINK gateway failed with HTTP ${response.status}`);
      }
      return body;
    } finally {
      clearTimeout(timeout);
    }
  }

  _validateResult(result, correlationId) {
    if (!result || typeof result !== 'object') {
      throw new Error('BRAINK gateway returned an invalid result envelope');
    }
    if (result.correlation_id !== correlationId) {
      throw new Error('BRAINK correlation mismatch');
    }
    if (result.protocol && result.protocol !== 'braink.adapter.v1') {
      throw new Error(`Unsupported BRAINK adapter protocol: ${result.protocol}`);
    }
    if (result.status === 'completed' && !result.proof) {
      throw new Error('BRAINK result claims completion without proof');
    }
  }

  _emit(name, detail) {
    if (typeof window !== 'undefined' && typeof CustomEvent !== 'undefined') {
      window.dispatchEvent(new CustomEvent(name, { detail }));
    }
  }
}

export function mountBRAINK(options = {}) {
  const adapter = new BRAINKAdapter(options);
  adapter.start();
  if (typeof window !== 'undefined') {
    window.BRAINK = adapter;
  }
  return adapter;
}
