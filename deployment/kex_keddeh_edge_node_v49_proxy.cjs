#!/usr/bin/env node
'use strict';
const http=require('http');
const {KeddehEdgeNode,EDGE_SCHEMA,routeRoot}=require('../kex_keddeh_edge_node_v48.cjs');

const ROUTES=[
 {host:'braink.com.au',path:'/runtime/recursive',match:'PREFIX',coordinate:'KEX://RUNTIME/BRAINK/RECURSIVE-COMPUTER/R26',contract:'R26_RECURSIVE_RUNTIME',upstream:'http://127.0.0.1:8811',stripPrefix:'/runtime/recursive'},
 {host:'braink.com.au',path:'/auth',match:'PREFIX',coordinate:'KEX://RAIL/BRAINK/GOOGLE-OAUTH',contract:'BRAINK_OAUTH',upstream:'http://127.0.0.1:8799'},
 {host:'braink.com.au',path:'/payments',match:'PREFIX',coordinate:'KEX://RAIL/BRAINK/STRIPE',contract:'BRAINK_PAYMENTS',upstream:'http://127.0.0.1:8799'},
 {host:'braink.com.au',path:'/',match:'PREFIX',coordinate:'KEX://DOMAIN-SPACE/BRAINK/USER',contract:'BRAINK_SITE',upstream:'http://127.0.0.1:8901'},
 {host:'braink-intelligence.com.au',path:'/runtime/recursive',match:'PREFIX',coordinate:'KEX://RUNTIME/BRAINK/RECURSIVE-COMPUTER/R26',contract:'R26_RECURSIVE_RUNTIME',upstream:'http://127.0.0.1:8811',stripPrefix:'/runtime/recursive'},
 {host:'braink-intelligence.com.au',path:'/',match:'PREFIX',coordinate:'KEX://DOMAIN-SPACE/BRAINK/INTELLIGENCE',contract:'BRAINK_INTELLIGENCE_SITE',upstream:'http://127.0.0.1:8902'},
 {host:'braink-learning.com.au',path:'/runtime/recursive',match:'PREFIX',coordinate:'KEX://RUNTIME/BRAINK/RECURSIVE-COMPUTER/R26',contract:'R26_RECURSIVE_RUNTIME',upstream:'http://127.0.0.1:8811',stripPrefix:'/runtime/recursive'},
 {host:'braink-learning.com.au',path:'/',match:'PREFIX',coordinate:'KEX://DOMAIN-SPACE/BRAINK/LEARNING',contract:'BRAINK_LEARNING_SITE',upstream:'http://127.0.0.1:8903'}
];

class KeddehEdgeNodeV49 extends KeddehEdgeNode{
 constructor(opts={}){super({...opts,routes:opts.routes||ROUTES});}
 _proxy(req,res,route,url){
  const target=new URL(route.upstream);
  let pathname=url.pathname;
  if(route.stripPrefix && pathname.startsWith(route.stripPrefix)) pathname=pathname.slice(route.stripPrefix.length)||'/';
  const options={hostname:target.hostname,port:target.port||80,method:req.method,path:pathname+(url.search||''),headers:{...req.headers,host:target.host,'x-kex-original-host':req.headers.host||'','x-kex-coordinate':route.coordinate}};
  const upstream=http.request(options,ur=>{
    const headers={...ur.headers,'x-kex-edge-node':this.state.node_id,'x-kex-coordinate':route.coordinate,'x-kex-contract':route.contract};
    res.writeHead(ur.statusCode||502,headers);ur.pipe(res);
  });
  upstream.on('error',err=>{
    this._receipt('UPSTREAM_FAILURE',{host:req.headers.host||'',path:url.pathname,kex_coordinate:route.coordinate,upstream:route.upstream,error:err.code||err.message,state:'FAILED'});
    if(!res.headersSent)this._send(res,502,{schema:'kex.edge.upstream.failure.v49',status:'UPSTREAM_FAILED',coordinate:route.coordinate,error:err.code||err.message},req.method);
    else res.end();
  });
  req.pipe(upstream);
 }
 _handle(req,res){
  const host=String(req.headers.host||'').split(':')[0].toLowerCase(); const url=new URL(req.url||'/','http://edge.local');
  if(url.pathname==='/__kex/edge/status'||url.pathname==='/__kex/edge/health') return super._handle(req,res);
  const route=this.resolve(host,url.pathname);this.state.request_sequence+=1;this._persist();
  if(!route){const receipt=this._receipt('INGRESS_UNRESOLVED',{host,path:url.pathname,state:'UNRESOLVED'});return this._send(res,404,{schema:'kex.edge.ingress.readback.v49',resolved:false,host,path:url.pathname,receipt},req.method);}
  const receipt=this._receipt('INGRESS_FORWARDED',{host,path:url.pathname,kex_coordinate:route.coordinate,contract:route.contract,upstream:route.upstream,state:'FORWARDING'});
  if(!route.upstream)return this._send(res,200,{schema:'kex.edge.ingress.readback.v49',resolved:true,host,path:url.pathname,kex_coordinate:route.coordinate,contract:route.contract,receipt},req.method);
  return this._proxy(req,res,route,url);
 }
 status(){return {...super.status(),schema:'kex.edge.status.v49',forwarding:true,upstreams:[...new Set(this.routes.map(r=>r.upstream).filter(Boolean))]};}
}
async function main(){const node=new KeddehEdgeNodeV49({host:process.env.KEX_EDGE_HOST||'0.0.0.0',port:Number(process.env.KEX_EDGE_PORT||8899),stateDir:process.env.KEX_EDGE_STATE_DIR||'.braink/edge-v49'});await node.start();console.log(JSON.stringify(node.status()));const stop=async()=>{await node.stop();process.exit(0)};process.on('SIGTERM',stop);process.on('SIGINT',stop);}
if(require.main===module)main().catch(e=>{console.error(e.stack||e);process.exit(1)});
module.exports={KeddehEdgeNodeV49,ROUTES};
