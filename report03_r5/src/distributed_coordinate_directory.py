#!/usr/bin/env python3
"""Process-separated KEX coordinate directory replicas driven only by committed ToT entries."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable
import json, multiprocessing as mp, os, socket, socketserver, sqlite3

from tot_safety_kernel import GENESIS_ROOT, canonical, h, is_global_quorum
from tot_process_cluster import ProcessCluster, TransportFault

SCHEMA = "keddeh.distributed-coordinate-directory.v2"
DIRECTORY_ID = "KEX://DIRECTORY/COORDINATES/DOMAIN-FABRIC/V2"
REPLICA_IDS = ("DIR_ALPHA", "DIR_BETA", "DIR_GAMMA")


def project_records(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for entry in entries:
        op, p = entry["operation"], entry["payload"]
        if op == "COORDINATE_DEFINE":
            coord = p["coordinate"]
            if coord in records: raise RuntimeError("REPLAY_DUPLICATE_COORDINATE")
            records[coord] = {
                "coordinate": coord, "kind": p["kind"], "authority_epoch": entry["term"],
                "defined_at_commit": entry["index"], "metadata": p.get("metadata", {}),
                "desired": p.get("desired", {}), "accepted_entry_root": entry["entry_root"],
            }
        elif op == "COORDINATE_DESIRED_SET":
            coord = p["coordinate"]
            if coord not in records: raise RuntimeError("REPLAY_UNKNOWN_COORDINATE")
            records[coord]["desired"] = p["desired"]
            records[coord]["authority_epoch"] = entry["term"]
            records[coord]["accepted_entry_root"] = entry["entry_root"]
            records[coord]["desired_commit"] = entry["index"]
        elif op == "COORDINATE_METADATA_PATCH":
            coord = p["coordinate"]
            if coord not in records: raise RuntimeError("REPLAY_UNKNOWN_COORDINATE")
            records[coord].setdefault("metadata", {}).update(p["patch"])
            records[coord]["authority_epoch"] = entry["term"]
            records[coord]["accepted_entry_root"] = entry["entry_root"]
    return records


def verify_committed_chain(entries: list[dict[str, Any]]) -> tuple[int, str]:
    prev = GENESIS_ROOT
    expected = 1
    for e in entries:
        if int(e["index"]) != expected or e["previous_root"] != prev:
            raise RuntimeError("DIRECTORY_SOURCE_CHAIN_INVALID")
        if not is_global_quorum(e.get("certificate", {}).get("voters", [])):
            raise RuntimeError("DIRECTORY_SOURCE_CERTIFICATE_INVALID")
        body = {k:e[k] for k in ["term","index","leader","previous_root","operation","payload","payload_root","proposal_root","certificate"]}
        if h(body) != e["entry_root"]:
            raise RuntimeError("DIRECTORY_SOURCE_ENTRY_ROOT_INVALID")
        prev = e["entry_root"]
        expected += 1
    return len(entries), prev


class DirectoryStore:
    def __init__(self, replica_id: str, db_path: str | Path):
        self.replica_id = replica_id
        self.db_path = Path(db_path); self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.executescript("""
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS records(coordinate TEXT PRIMARY KEY, body_json TEXT NOT NULL);
        """)
        with self.conn:
            for k,v in {"schema":SCHEMA,"replica_id":replica_id,"applied_commit_index":"0","accepted_state_root":GENESIS_ROOT}.items():
                self.conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)",(k,v))

    def _get(self,k:str)->str:
        return str(self.conn.execute("SELECT value FROM meta WHERE key=?",(k,)).fetchone()[0])
    def _set(self,k:str,v:str)->None:
        self.conn.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))

    def snapshot(self)->dict[str,Any]:
        records={r["coordinate"]:json.loads(r["body_json"]) for r in self.conn.execute("SELECT coordinate,body_json FROM records ORDER BY coordinate")}
        body={"schema":SCHEMA,"directory_id":DIRECTORY_ID,"replica_id":self.replica_id,"applied_commit_index":int(self._get("applied_commit_index")),"accepted_state_root":self._get("accepted_state_root"),"records":records}
        # Replica id is excluded from content root so converged replicas can compare equal authority projections.
        root_body={k:v for k,v in body.items() if k!="replica_id"}
        body["directory_root"]=h(root_body)
        body["pid"]=os.getpid()
        body["sqlite"]={"journal_mode":str(self.conn.execute("PRAGMA journal_mode").fetchone()[0]).upper(),"synchronous":int(self.conn.execute("PRAGMA synchronous").fetchone()[0]),"db_path":str(self.db_path)}
        return body

    def apply_log(self, entries:list[dict[str,Any]])->dict[str,Any]:
        idx, root=verify_committed_chain(entries)
        records=project_records(entries)
        with self.conn:
            self.conn.execute("DELETE FROM records")
            for coord, body in sorted(records.items()):
                self.conn.execute("INSERT INTO records(coordinate,body_json) VALUES(?,?)",(coord,canonical(body)))
            self._set("applied_commit_index",str(idx)); self._set("accepted_state_root",root)
        return self.snapshot()

    def resolve(self,coordinate:str)->dict[str,Any]:
        row=self.conn.execute("SELECT body_json FROM records WHERE coordinate=?",(coordinate,)).fetchone()
        snap=self.snapshot()
        if not row: return {"state":"NOT_FOUND","coordinate":coordinate,"directory_root":snap["directory_root"],"accepted_state_root":snap["accepted_state_root"],"commit_index":snap["applied_commit_index"]}
        return {"state":"RESOLVED_ACCEPTED_COORDINATE","coordinate":coordinate,"record":json.loads(row[0]),"directory_root":snap["directory_root"],"accepted_state_root":snap["accepted_state_root"],"commit_index":snap["applied_commit_index"]}

    def handle(self,req:dict[str,Any])->dict[str,Any]:
        op=req.get("op")
        if op=="APPLY_LOG": return self.apply_log(req.get("entries",[]))
        if op=="STATE": return self.snapshot()
        if op=="RESOLVE": return self.resolve(req["coordinate"])
        if op=="PING": return {"pong":True,"replica_id":self.replica_id,"pid":os.getpid()}
        raise ValueError(f"UNKNOWN_DIRECTORY_RPC:{op}")


class _Server(socketserver.TCPServer): allow_reuse_address=True
class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            req=json.loads(self.rfile.readline(8*1024*1024).decode())
            out=self.server.store.handle(req) # type: ignore[attr-defined]
            self.wfile.write((canonical({"ok":True,"result":out})+"\n").encode())
        except Exception as exc:
            self.wfile.write((canonical({"ok":False,"error":type(exc).__name__,"message":str(exc)})+"\n").encode())

def _serve(replica_id:str,db_path:str,q:mp.Queue)->None:
    store=DirectoryStore(replica_id,db_path); srv=_Server(("127.0.0.1",0),_Handler); srv.store=store # type: ignore[attr-defined]
    q.put({"replica_id":replica_id,"port":srv.server_address[1],"pid":os.getpid()})
    try: srv.serve_forever(poll_interval=.05)
    finally: store.conn.close(); srv.server_close()


class DirectoryCluster:
    def __init__(self,root:str|Path,source:ProcessCluster):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.source=source
        self.processes:dict[str,mp.Process]={}; self.ports:dict[str,int]={}; self.pids:dict[str,int]={}
        for r in REPLICA_IDS: self.start(r)
    def _path(self,r): return self.root/f"{r}.sqlite3"
    def start(self,r):
        if r in self.processes and self.processes[r].is_alive(): return
        ctx=mp.get_context("forkserver"); q=ctx.Queue(); p=ctx.Process(target=_serve,args=(r,str(self._path(r)),q),daemon=True); p.start(); info=q.get(timeout=5)
        self.processes[r]=p; self.ports[r]=int(info["port"]); self.pids[r]=int(info["pid"]); self._rpc(r,{"op":"PING"})
    def kill(self,r):
        p=self.processes.get(r)
        if p and p.is_alive(): p.terminate(); p.join(timeout=2)
        self.processes.pop(r,None); self.ports.pop(r,None)
    def restart(self,r): self.kill(r); self.start(r)
    def stop(self):
        for r in list(self.processes): self.kill(r)
    def __enter__(self): return self
    def __exit__(self,*_): self.stop()
    def _rpc(self,r,req):
        if r not in self.ports: raise TransportFault(f"DIRECTORY_DOWN:{r}")
        try:
            with socket.create_connection(("127.0.0.1",self.ports[r]),timeout=1.5) as s:
                s.sendall((canonical(req)+"\n").encode()); line=s.makefile("rb").readline(8*1024*1024); out=json.loads(line.decode())
                if not out.get("ok"): raise RuntimeError(f"DIRECTORY_REMOTE_{out.get('error')}:{out.get('message')}")
                return out["result"]
        except OSError as exc: raise TransportFault(f"DIRECTORY_RPC_FAILED:{r}:{exc}") from exc
    def sync(self, replicas:Iterable[str]=REPLICA_IDS)->dict[str,Any]:
        entries=self.source.canonical_committed_log(); out={}
        for r in replicas:
            if r in self.ports: out[r]=self._rpc(r,{"op":"APPLY_LOG","entries":entries})
        return out
    def state(self,r): return self._rpc(r,{"op":"STATE"})
    def resolve(self,r,coordinate): return self._rpc(r,{"op":"RESOLVE","coordinate":coordinate})
    def roots(self)->dict[str,str]: return {r:self.state(r)["directory_root"] for r in REPLICA_IDS if r in self.ports}
    def converged(self)->bool:
        roots=list(self.roots().values()); return bool(roots) and len(set(roots))==1