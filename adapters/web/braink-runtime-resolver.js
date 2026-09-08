export class BRAINKRuntimeResolver {
  constructor(manifest, transports = {}) {
    this.manifest = manifest;
    this.transports = transports;
  }

  resolve(task = {}) {
    const requirements = new Set(task.requirements || []);

    if (requirements.has('workbook') || requirements.has('sheet')) {
      return this._surface('workbook');
    }
    if (requirements.has('linux') || requirements.has('process')) {
      return this._surface('linux');
    }
    if (requirements.has('ai') || requirements.has('inference')) {
      return this._surface('ai');
    }
    if (requirements.has('vfs') || requirements.has('file') || requirements.has('persistence')) {
      return this._surface('vfs');
    }

    return this._surface('api');
  }

  async dispatch(task = {}, envelope = {}) {
    const surface = this.resolve(task);
    const transport = this.transports[surface.class] || this.transports[surface.role];

    if (typeof transport !== 'function') {
      throw new Error(`No transport bound for resident surface ${surface.class}:${surface.address || surface.role}`);
    }

    return transport({
      surface,
      task,
      envelope,
      pipeline: this.manifest.dispatch_pipeline,
      authority: this.manifest.authority
    });
  }

  _surface(name) {
    const surface = this.manifest?.resident_surfaces?.[name];
    if (!surface) {
      throw new Error(`Unknown BRAINK resident surface: ${name}`);
    }
    return { name, ...surface };
  }
}

export function createDefaultBRAINKTransports(options = {}) {
  const apiBase = options.apiBase || '';

  return {
    api_server: async ({ task, envelope }) => {
      const response = await fetch(`${apiBase}/v1/compile`, {
        method: 'POST',
        headers: { 'content-type': 'application/json', ...(options.headers || {}) },
        body: JSON.stringify({ task, envelope })
      });
      if (!response.ok) throw new Error(`BRAINK API runtime failed: HTTP ${response.status}`);
      return response.json();
    },

    workbook_runtime: async context => {
      if (!options.workbookDispatch) {
        throw new Error('Workbook runtime selected but no workbookDispatch binding is installed');
      }
      return options.workbookDispatch(context);
    },

    linux_runtime: async context => {
      if (!options.linuxDispatch) {
        throw new Error('Linux runtime selected but no linuxDispatch binding is installed');
      }
      return options.linuxDispatch(context);
    },

    ai_server: async context => {
      if (!options.aiDispatch) {
        throw new Error('AI server selected but no aiDispatch binding is installed');
      }
      return options.aiDispatch(context);
    },

    vfs: async context => {
      if (!options.vfsDispatch) {
        throw new Error('VFS selected but no vfsDispatch binding is installed');
      }
      return options.vfsDispatch(context);
    }
  };
}
