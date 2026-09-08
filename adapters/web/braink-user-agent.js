import { BRAINKAdapter } from './braink-web-adapter.js';

export class BRAINKUserAgent {
  constructor(options = {}) {
    this.adapter = options.adapter || new BRAINKAdapter(options);
    this.userId = options.userId || null;
    this.sessionId = options.sessionId || crypto.randomUUID();
    this.permissions = new Set(options.permissions || []);
    this.context = options.context || {};
    this.started = false;
  }

  async start() {
    if (this.started) return this;
    await this.adapter.start();
    this.started = true;
    this._emit('braink:user-agent:ready', {
      session_id: this.sessionId,
      user_id: this.userId,
      permissions: [...this.permissions]
    });
    return this;
  }

  grant(permission) {
    this.permissions.add(permission);
    this._emit('braink:user-agent:permission', {
      action: 'granted',
      permission,
      session_id: this.sessionId
    });
    return this;
  }

  revoke(permission) {
    this.permissions.delete(permission);
    this._emit('braink:user-agent:permission', {
      action: 'revoked',
      permission,
      session_id: this.sessionId
    });
    return this;
  }

  has(permission) {
    return this.permissions.has(permission);
  }

  async ask(intent, payload = {}, options = {}) {
    if (!this.started) await this.start();

    const required = options.permission;
    if (required && !this.permissions.has(required)) {
      throw new Error(`BRAINK user permission required: ${required}`);
    }

    const userEnvelope = {
      ...payload,
      _braink_user: {
        user_id: this.userId,
        session_id: this.sessionId,
        permissions: [...this.permissions],
        context: this.context,
        interaction: options.interaction || 'user-initiated'
      }
    };

    return this.adapter.dispatch(intent, userEnvelope, {
      ...options,
      capabilities: options.capabilities || [],
      proofRequired: options.proofRequired !== false
    });
  }

  async tool(toolName, args = {}, options = {}) {
    const permission = options.permission || `tool:${toolName}`;
    return this.ask('braink.tool.invoke', {
      tool: toolName,
      arguments: args
    }, {
      ...options,
      permission
    });
  }

  async task(task, options = {}) {
    return this.ask('braink.task.execute', {
      task,
      mode: options.mode || 'agentic',
      constraints: options.constraints || {},
      expected_artifacts: options.expectedArtifacts || []
    }, options);
  }

  async explain(receiptId, options = {}) {
    return this.ask('braink.receipt.explain', {
      receipt_id: receiptId
    }, {
      ...options,
      proofRequired: false
    });
  }

  _emit(name, detail) {
    if (typeof window !== 'undefined' && typeof CustomEvent !== 'undefined') {
      window.dispatchEvent(new CustomEvent(name, { detail }));
    }
  }
}

export function mountBRAINKUserAgent(options = {}) {
  const agent = new BRAINKUserAgent(options);
  agent.start();
  if (typeof window !== 'undefined') {
    window.BRAINK_USER = agent;
  }
  return agent;
}
