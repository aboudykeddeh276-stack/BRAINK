#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const file=path.resolve(process.argv[2]||path.join(here,'index.html'));
const port=Number(process.env.PORT||process.argv[3]||8787),host=process.env.HOST||'127.0.0.1';
if(!fs.existsSync(file)){console.error(JSON.stringify({state:'REJECT',reason:'MISSING_HTML',file}));process.exit(2)}
const data=fs.readFileSync(file),sha=crypto.createHash('sha256').update(data).digest('hex');
const receipt={schema:'kex.host.adapter.portable.v2',logical_machine:'volume://keddeh/braink/root',machine_contract:'machine://kex/hardware-contract',platform:process.platform,arch:process.arch,hostname:os.hostname(),file,bytes:data.length,sha256:sha,host,port,module_contract:'ESM'};
const server=http.createServer((req,res)=>{if(req.url==='/'||req.url==='/index.html'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Content-Length':data.length,'Cache-Control':'no-store'});res.end(data)}else if(req.url==='/__kex_receipt'){res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify({...receipt,state:'SERVING'}))}else{res.writeHead(404);res.end('not found')}});
server.listen(port,host,()=>console.log(JSON.stringify({...receipt,state:'SERVING',url:`http://${host}:${port}/`})));
