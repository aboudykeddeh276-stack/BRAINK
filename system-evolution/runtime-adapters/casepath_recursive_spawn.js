const fs = require("fs");
const vm = require("vm");
const crypto = require("crypto");

function stub() {
  const cls = { toggle(){}, add(){}, remove(){} };
  return new Proxy({
    style:{}, classList:cls, dataset:{}, children:[], value:"", checked:false,
    disabled:false, innerHTML:"", textContent:"", innerText:"", files:[],
    appendChild(){}, remove(){}, addEventListener(){}, setAttribute(){},
    getAttribute(){ return null; }, click(){}, focus(){}
  }, { get(t,p) {
    if (p in t) return t[p];
    if (p === "querySelectorAll") return () => [];
    if (p === "querySelector") return () => null;
    return undefined;
  }});
}

function makeContext(label) {
  const store = new Map(), nodes = new Map();
  const document = {
    body: stub(),
    getElementById(id){ if(!nodes.has(id)) nodes.set(id, stub()); return nodes.get(id); },
    querySelectorAll(){ return []; }, querySelector(){ return null; },
    createElement(){ return stub(); }, addEventListener(){}
  };
  const localStorage = {
    getItem:k => store.has(k) ? store.get(k) : null,
    setItem:(k,v) => store.set(k,String(v)), removeItem:k => store.delete(k), clear:()=>store.clear()
  };
  const ctx = {
    console, document, localStorage, sessionStorage:localStorage,
    structuredClone, Blob, TextEncoder, TextDecoder, atob, btoa,
    crypto:crypto.webcrypto, performance:{now:()=>Date.now()},
    setTimeout:(fn,ms)=>0, clearTimeout(){}, navigator:{},
    location:{reload(){}, href:"runtime://"+label}, confirm:()=>true,
    URL:{createObjectURL(){return "blob:stub"}, revokeObjectURL(){}},
    fetch:async()=>{ throw new Error("NETWORK_DISABLED_IN_RECURSIVE_TEST"); }
  };
  ctx.window = ctx; ctx.globalThis = ctx; ctx.self = ctx;
  return vm.createContext(ctx);
}

const runtimeSource = fs.readFileSync(process.argv[2], "utf8");
const children = new Map();

async function instantiate(label, parent=null, generation=0) {
  const context = makeContext(label);
  vm.runInContext(runtimeSource, context, {filename:label+".runtime.js", timeout:10000});
  const cp = context.CasePathOS;
  if (!cp) throw new Error(label+": CasePathOS export missing");
  await cp.boot();
  await cp.meshBoot();

  if (parent) {
    cp.mount("/system/lineage/parent.json", {
      schema:"kex.casepath.runtime-parent.v1",
      parent_label:parent.label,
      parent_runtime_id:parent.cp.kernel.runtimeId,
      parent_runtime_root:parent.cp.kernel.runtimeRoot,
      generation,
      relation:"INSTANTIATED_BY"
    }, {kind:"lineage"});
    await cp.receipt("RUNTIME_PARENT_BOUND", {
      parent_label:parent.label,
      parent_runtime_id:parent.cp.kernel.runtimeId,
      generation
    });
  }

  const node = {label, context, cp, generation};
  cp.kernel.capabilities.set("CP_RUNTIME_CONSTRUCTOR", Object.freeze({
    authority:"LOCAL", matterData:false, recursive:true, inherited:true, name:"CP_RUNTIME_CONSTRUCTOR"
  }));

  cp.kernel.services.set("RUNTIME.SPAWN", async ({child_label}) => {
    if (!child_label) throw new Error("child_label required");
    const child = await instantiate(child_label, node, generation + 1);
    children.set(child_label, child);
    cp.mount("/system/descendants/"+child_label+".json", {
      child_label,
      child_runtime_id:child.cp.kernel.runtimeId,
      child_runtime_root:child.cp.kernel.runtimeRoot,
      generation:generation+1,
      state:"BOOTED_MESHED_CHECKPOINTED"
    }, {kind:"descendant"});
    await cp.receipt("RUNTIME_DESCENDANT_INSTANTIATED", {
      child_label,
      child_runtime_id:child.cp.kernel.runtimeId,
      generation:generation+1
    });
    return {child_label, runtime_id:child.cp.kernel.runtimeId, runtime_root:child.cp.kernel.runtimeRoot, generation:generation+1};
  });

  cp.mount("/system/capabilities/runtime-constructor.json",
    cp.kernel.capabilities.get("CP_RUNTIME_CONSTRUCTOR"), {kind:"capability"});
  await cp.receipt("RUNTIME_CONSTRUCTOR_READY", {generation, runtime_id:cp.kernel.runtimeId});
  const checkpoint = await cp.call("RECOVERY.CHECKPOINT", {label:"recursive-generation-"+generation});
  return {...node, checkpoint};
}

module.exports = { instantiate, children };
