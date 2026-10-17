#!/usr/bin/env node
'use strict';

const http=require('http');
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');

const SCHEMA='kex.edge.node.v49';
const MAX_BODY_BYTES=Number(process.env.KEX_EDGE_MAX_BODY_BYTES||1048576);
const HOP_BY_HOP=new Set(['connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','transfer-encoding','upgrade']);

const ROUTES=[
 {host:'braink.com.au',path:'/runtime/recursive',coordinate:'KEX://RUNTIME/BRAINK/RECURSIVE-COMPUTER/R26',contract:'R26_RECURSIVE_RUNTIME',upstream:'http://127.0.0.1:8811',stripPrefix:'/runtime/recursive',policy:'PUBLIC_READ_ADMIN_WRITE'},
 {host:'braink.com.au',path:'/auth',coordinate:'KEX://RAIL/BRAINK/GOOGLE-OAUTH',contract:'BRAINK_OAUTH',upstream:'http://127.0.0.1:8799',policy:'PUBLIC'},
 {host:'braink.com.au',path:'/payments',coordinate:'KEX://RAIL/BRAINK/STRIPE',contract:'BRAINK_PAYMENTS',upstream:'http://127.0.0.1:8799',policy:'PUBLIC'},
 {host:'braink.com.au',path:'/',coordinate:'KEX://DOMAIN-SPACE/BRAINK/USER',contract:'BRAINK_SITE',upstream:'http://127.0.0.1:8901',policy:'PUBLIC'},
 {host:'braink-intelligence.com.au',path:'/runtime/recursive',coordinate:'KEX://RUNTIME/BRAINK/RECURSIVE-COMPUTER/R26',contract:'R26_RECURSIVE_RUNTIME',upstream:'http://127.0.0.1:8811',stripPrefix:'/runtime/recursive',policy:'PUBLIC_READ_ADMIN_WRITE'},
 {host:'braink-intelligence.com.au',path:'/',coordinate:'KEX://DOMAIN-SPACE/BRAINK/INTELLIGENCE',contract:'BRAINK_INTELLIGENCE_SITE',upstream:'http://127.0.0.1:8902',policy:'PUBLIC'},
 {host:'braink-learning.com.au',path:'/runtime/recursive',coordinate:'KEX://RUNTIME/BRAINK/RECURSIVE-COMPUTER/R26',contract:'R26_RECURSIVE_RUNTIME',upstream:'http://127.0.0.1:8811',stripPrefix:'/runtime/recursive',policy:'PUBLIC_READ_ADMIN_WRITE'},
 {host:'braink-learning.com.au',path:'/',coordinate:'KEX://DOMAIN-SPACE/BRAINK/LEARNING',contract:'BRAINK_LEARNING_SITE',upstream:'http://127.0.0.1:8903',policy:'PUBLIC'}
];

function stable(v){if(Array.isArray(v))return '['+v.map(stable).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stable(v[k])).join(',')+'}';return JSON.stringify(v)}
function sha(v){return crypto.createHash('sha256').update(typeof v==='string'?v:stable(v)).digest('hex')}
function hostOnly(v=''){const s=String(v).trim().toLowerCase();if(s.startsWith('[')){const i=s.indexOf(']');return i>=0?s.slice(1,i):s}return s.split(':')[0]}
function pathMatches(routePath,p){return routePath==='/'||p===routePath||p.startsWith(routePath+'/')}
function loopback(addr=''){return addr==='127.0.0.1'||addr==='::1'||addr==='::ffff:127.0.0.1'}
function bearer(req){const h=String(req.headers.authorization||'');return h.startsWith('Bearer ')?h.slice(7):h}
function tokenEqual(a,b){const x=Buffer.from(String(a||'')),y=Buffer.from(String(b||''));return x.length===y.length&&x.length>0&&crypto.timingSafeEqual(x,y)}
function filteredHeaders(headers){const out={};for(const [k,v] of Object.entries(headers)){if(!HOP_BY_HOP.has(k.toLowerCase())&&k.toLowerCase()!=='host'&&k.toLowerCase()!=='authorization')out[k]=v}return out}
function loadSecret(envName,fileEnvName){const file=process.env[fileEnvName];const value=file?fs.readFileSync(file,'utf8').trim():(process.env[envName]||'');if(value&&value.length<32)throw new Error(envName+'_TOO_SHORT');return value}
function atomic(file,obj){
 fs.mkdirSync(path.dirname(file),{recursive:true});
 const tmp=file+'.tmp-'+process.pid+'-'+crypto.randomBytes(4).toString('hex');
 let fd;
 try{
  fd=fs.openSync(tmp,'w',0o600);fs.writeFileSync(fd,JSON.stringify(obj,null,2));fs.fsyncSync(fd);fs.closeSync(fd);fd=undefined;
  fs.renameSync(tmp,file);
  const dfd=fs.openSync(path.dirname(file),'r');try{fs.fsyncSync(dfd)}finally{fs.closeSync(dfd)}
 }finally{if(fd!==undefined)try{fs.closeSync(fd)}catch{};if(fs.existsSync(tmp))try{fs.unlinkSync(tmp)}catch{}}
}

class Edge{
 constructor(){
  this.host=process.env.KEX_EDGE_HOST||'0.0.0.0';
  this.port=Number(process.env.KEX_EDGE_PORT||8899);
  this.stateDir=path.resolve(process.env.KEX_EDGE_STATE_DIR||'.braink/edge-v49');
  this.stateFile=path.join(this.stateDir,'edge-state.json');
  this.receiptFile=path.join(this.stateDir,'edge-receipts.jsonl');
  this.adminToken=loadSecret('KEX_EDGE_ADMIN_TOKEN','KEX_EDGE_ADMIN_TOKEN_FILE');
  this.r26ServiceToken=loadSecret('KEX_R26_SERVICE_TOKEN','KEX_R26_SERVICE_TOKEN_FILE');
  fs.mkdirSync(this.stateDir,{recursive:true});
  this.state=fs.existsSync(this.stateFile)?JSON.parse(fs.readFileSync(this.stateFile)):{schema:SCHEMA,node_id:'kex-edge-'+crypto.randomBytes(12).toString('hex'),created_at:new Date().toISOString(),boot_sequence:0,heartbeat_sequence:0,request_sequence:0,route_root:sha(ROUTES),lifecycle:'CREATED',external:{public_name_authority:'UNBOUND',authoritative_dns:'UNBOUND',tls_identity:'UNBOUND',public_ingress:'LOCAL_ONLY'}};
  this.server=null;this.timer=null;
 }
 persist(){this.state.route_root=sha(ROUTES);atomic(this.stateFile,this.state)}
 receipt(type,data={}){const r={schema:'kex.edge.receipt.v49',type,node_id:this.state.node_id,time:new Date().toISOString(),boot_sequence:this.state.boot_sequence,heartbeat_sequence:this.state.heartbeat_sequence,request_sequence:this.state.request_sequence,...data};fs.appendFileSync(this.receiptFile,JSON.stringify(r)+'\n');return r}
 resolve(host,p){return ROUTES.filter(r=>r.host===host&&pathMatches(r.path,p)).sort((a,b)=>b.path.length-a.path.length)[0]||null}
 status(){const a=this.server&&this.server.address();return {schema:SCHEMA,node_id:this.state.node_id,lifecycle:this.state.lifecycle,physical_listener_count:this.server?1:0,logical_service_count:ROUTES.length,route_root:this.state.route_root,bind:a&&typeof a==='object'?{address:a.address,port:a.port,family:a.family}:null,transport_mode:'HTTP_LOCAL_PROOF',external:{...this.state.external},heartbeat_sequence:this.state.heartbeat_sequence,boot_sequence:this.state.boot_sequence,forwarding:true,upstreams:[...new Set(ROUTES.map(r=>r.upstream))],recursive_mutation_policy:'ADMIN_BEARER_REQUIRED'} }
 send(res,code,obj,method){const b=Buffer.from(JSON.stringify(obj));res.writeHead(code,{'content-type':'application/json','content-length':String(b.length),'cache-control':'no-store','x-kex-edge-node':this.state.node_id});method==='HEAD'?res.end():res.end(b)}
 adminAllowed(req){return Boolean(this.adminToken)&&tokenEqual(bearer(req),this.adminToken)}
 routeAllowed(req,route){if(route.policy!=='PUBLIC_READ_ADMIN_WRITE')return true;if(req.method==='GET'||req.method==='HEAD')return true;return this.adminAllowed(req)}
 proxy(req,res,route,u){
  const t=new URL(route.upstream);let p=u.pathname;
  if(route.stripPrefix&&p.startsWith(route.stripPrefix))p=p.slice(route.stripPrefix.length)||'/';
  const headers={...filteredHeaders(req.headers),host:t.host,'x-kex-original-host':req.headers.host||'','x-kex-coordinate':route.coordinate};
  if(route.policy==='PUBLIC_READ_ADMIN_WRITE'&&this.r26ServiceToken)headers.authorization='Bearer '+this.r26ServiceToken;
  const q=http.request({hostname:t.hostname,port:t.port||80,method:req.method,path:p+u.search,headers},ur=>{
   const out=filteredHeaders(ur.headers);out['x-kex-edge-node']=this.state.node_id;out['x-kex-coordinate']=route.coordinate;out['x-kex-contract']=route.contract;
   res.writeHead(ur.statusCode||502,out);ur.pipe(res)
  });
  q.on('error',e=>{this.receipt('UPSTREAM_FAILURE',{host:hostOnly(req.headers.host),path:u.pathname,kex_coordinate:route.coordinate,upstream:route.upstream,error:e.code||e.message,state:'FAILED'});if(!res.headersSent)this.send(res,502,{status:'UPSTREAM_FAILED',coordinate:route.coordinate,error:e.code||e.message},req.method);else res.end()});
  req.pipe(q)
 }
 handle(req,res){
  const host=hostOnly(req.headers.host),u=new URL(req.url||'/','http://edge.local');this.state.request_sequence++;this.persist();
  if(u.pathname==='/__kex/edge/health')return this.send(res,200,{state:'READY',node_id:this.state.node_id,heartbeat_sequence:this.state.heartbeat_sequence},req.method);
  if(u.pathname==='/__kex/edge/status'){
   if(!loopback(req.socket.remoteAddress)&&!this.adminAllowed(req))return this.send(res,403,{status:'REJECTED',reason:'EDGE_STATUS_ADMIN_REQUIRED'},req.method);
   return this.send(res,200,this.status(),req.method)
  }
  const r=this.resolve(host,u.pathname);
  if(!r)return this.send(res,404,{status:'UNRESOLVED',host,path:u.pathname,receipt:this.receipt('INGRESS_UNRESOLVED',{host,path:u.pathname})},req.method);
  const length=Number(req.headers['content-length']||0);if(Number.isFinite(length)&&length>MAX_BODY_BYTES)return this.send(res,413,{status:'REJECTED',reason:'REQUEST_BODY_TOO_LARGE',max_body_bytes:MAX_BODY_BYTES},req.method);
  if(!this.routeAllowed(req,r)){
   const receipt=this.receipt('INGRESS_REJECTED',{host,path:u.pathname,kex_coordinate:r.coordinate,contract:r.contract,reason:'ADMIN_MUTATION_AUTH_REQUIRED'});
   return this.send(res,403,{status:'REJECTED',reason:'ADMIN_MUTATION_AUTH_REQUIRED',receipt},req.method)
  }
  this.receipt('INGRESS_FORWARDED',{host,path:u.pathname,kex_coordinate:r.coordinate,contract:r.contract,upstream:r.upstream,state:'FORWARDING'});
  return this.proxy(req,res,r,u)
 }
 async start(){
  this.state.boot_sequence++;this.state.lifecycle='BOOTING';this.persist();
  this.server=http.createServer((q,s)=>this.handle(q,s));this.server.maxHeadersCount=64;this.server.headersTimeout=10000;this.server.requestTimeout=30000;this.server.keepAliveTimeout=5000;
  await new Promise((ok,no)=>{this.server.once('error',no);this.server.listen(this.port,this.host,ok)});
  this.state.lifecycle='READY';this.persist();this.receipt('EDGE_BOOT_COMPLETED',{state:'COMPLETED',claim_boundary:'FINITE_LISTENER_ROUTE_AND_UPSTREAM_READBACK'});
  this.timer=setInterval(()=>{this.state.heartbeat_sequence++;this.persist()},1000);this.timer.unref?.();return this.status()
 }
 async stop(){if(this.timer)clearInterval(this.timer);if(this.server)await new Promise(r=>this.server.close(r));this.state.lifecycle='STOPPED';this.persist()}
}

async function main(){const e=new Edge();console.log(JSON.stringify(await e.start()));const stop=async()=>{await e.stop();process.exit(0)};process.on('SIGTERM',stop);process.on('SIGINT',stop)}
if(require.main===module)main().catch(e=>{console.error(e.stack||e);process.exit(1)});
module.exports={Edge,ROUTES,SCHEMA,pathMatches,hostOnly};
