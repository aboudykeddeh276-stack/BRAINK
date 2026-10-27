/**
 * Execute the actual source-bound BRAINK V4 polygon algorithm with its V5 R22
 * wrapper restored, outside a browser, and export its real learning candidates.
 * No synthetic polygon fixtures, no external-executor claim, no global promotion.
 * Architect: A. Keddeh / KEDDEH Systems.
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const dir=path.dirname(fileURLToPath(import.meta.url));
const sourcePath=path.join(dir,'KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html');
const carrierPath=path.join(dir,'KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4_HOST_LINK.html');
const outPath=path.resolve(process.argv[2]||'./v4_native_execution.json');
const statePath=path.resolve(process.argv[3]||'./v4_native_state.json');
const raw=fs.readFileSync(sourcePath);
const sourceHash=crypto.createHash('sha256').update(raw).digest('hex');
if(sourceHash!=='3cf4c7713e2fa4e38cfba840336854b3e488c899c35fd27e7a21e376b910b1d3')throw Error('HISTORICAL_V4_SHA_MISMATCH');
const html=fs.readFileSync(carrierPath,'utf8');
const js=html.split('<script>')[1]?.split('</script>')[0];
if(!js||!js.includes('/* BEGIN SOURCE-EXACT V5 WRAPPER FUNCTIONS'))throw Error('V5_R22_CONTROL_NOT_BOUND');
if(!js.includes(sourceHash))throw Error('MIRROR_SOURCE_SHA_MISMATCH');
const elements=new Map();
function element(k){if(!elements.has(k)){const el={value:'',textContent:'',innerHTML:'',checked:true,disabled:false,style:{},classList:{add(){},remove(){}},children:[],addEventListener(){},appendChild(child){this.children.push(child);return child},focus(){},scrollHeight:0,scrollTop:0};
if(k==='#agentDepth')el.value='standard';
if(k==='#chat')el.innerHTML='';
elements.set(k,el);}return elements.get(k)}
const document={querySelector:element,createElement:()=>element('created-'+crypto.randomUUID())};
const storage={getItem(key){try{return JSON.parse(fs.readFileSync(statePath,'utf8'))[key]??null}catch{return null}},setItem(key,val){let saved={};try{saved=JSON.parse(fs.readFileSync(statePath,'utf8'))}catch{}saved[key]=val;const tmp=statePath+'.tmp.'+process.pid;fs.writeFileSync(tmp,JSON.stringify(saved));fs.renameSync(tmp,statePath)}};
const context=vm.createContext({document,localStorage:storage,crypto,location:{protocol:'file:'},URL,console,Date,Math,JSON,Map,Set,Blob,clearInterval,setInterval,setTimeout,clearTimeout});
const marked=js.replace(/\}\)\(\);\s*$/,`globalThis.__V4_NATIVE={run100GrowthPasses,state:()=>S};\n})();`);
if(marked===js)throw Error('V4_ENTRY_BINDING_NOT_FOUND');
vm.runInContext(marked,context,{filename:'source-bound-V4-V5-control.js',timeout:10000});
const result=await vm.runInContext('globalThis.__V4_NATIVE.run100GrowthPasses()',context,{timeout:10000});
const state=JSON.parse(vm.runInContext('JSON.stringify(globalThis.__V4_NATIVE.state())',context));
if(!result?.admitted||result?.receipt?.mirrorResult!=='MATCH'||result?.result?.passes!==100)throw Error('POLYGON_R22_ADMISSION_OR_EXECUTION_FAILED');
if(state.polygonState?.iteration!==100||state.polygonState.history.length!==100)throw Error('POLYGON_SUCCESSOR_COUNT_MISMATCH');
const entries=state.hostLink?.pending||[];
const growth=entries.filter(x=>x.v4_receipt?.type==='POLYGON_100_ITERATION');
if(growth.length!==100||entries.length!==101)throw Error(`ORIGINAL_V4_MIRROR_CANDIDATE_COUNT_MISMATCH:${growth.length}/${entries.length}`);
if(growth.some((x,i)=>x.polygon.iteration!==i+1||x.polygon.lastSuccessor!==`①_${i+1}`||!x.observer.stateFormula))throw Error('ORIGINAL_V4_OBSERVER_SUCCESSOR_INVARIANT_FAILED');
const payload={schema:'KS-BRAINK-IL-LLM/native-original-v4-100passes/1',source_sha256:sourceHash,control_source_sha256:'ccbaf267a40b3f55b56da6b7f97c77279bdd583d29d1aa27139d085f5acd117b',source_kind:'ORIGINAL_V4_REAL_JS_ALGORITHM_NODE_VM_WITH_DOM_STORAGE_ADAPTER',scope:'LOCAL_NODE_PROCESS_NOT_CHROMIUM_OR_EXTERNAL_KEDDEH_HOST',admission:result.admitted,mirror:result.receipt.mirrorResult,passes:result.result.passes,iteration:state.polygonState.iteration,history_digest_v4:result.result.historyDigest,last_successor:result.result.lastSuccessor,lexicon_count:Object.keys(state.lexicon).length,corpus_count:state.corpus.length,mirror_candidates:entries.length,instance_id:state.hostLink.instanceId,records:entries,verification:'CANDIDATES_GENERATED_NOT_YET_TRANSPORT_COMMITTED',promotion_state:'NOT_PROMOTED'};
fs.writeFileSync(outPath,JSON.stringify(payload,null,2)+'\n');
console.log(JSON.stringify({status:'PASS',source_hash:sourceHash,passes:payload.passes,mirror:payload.mirror,iteration:payload.iteration,candidates:entries.length,last_successor:payload.last_successor,output:outPath}));
