from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
import hashlib, json, os, urllib.request


def canonical(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(v: Any) -> str:
    return hashlib.sha256(canonical(v).encode()).hexdigest()


class EnvironmentProbe:
    name: str
    def sample(self) -> Mapping[str, Any]:
        raise NotImplementedError


@dataclass
class FileSystemProbe(EnvironmentProbe):
    name: str
    root_path: Path
    paths: tuple[str, ...]
    def sample(self) -> Mapping[str, Any]:
        base=self.root_path.resolve(); out={}
        for rel in self.paths:
            p=(base/rel).resolve()
            if p != base and base not in p.parents:
                out[rel]={"exists":False,"error":"OUT_OF_SCOPE"}; continue
            if not p.exists(): out[rel]={"exists":False}; continue
            b=p.read_bytes() if p.is_file() else b""
            out[rel]={"exists":True,"kind":"file" if p.is_file() else "directory","sha256":hashlib.sha256(b).hexdigest() if p.is_file() else None,"bytes":len(b) if p.is_file() else None}
        return {"root":str(base),"paths":out}


@dataclass
class ProcessProbe(EnvironmentProbe):
    name: str = "process"
    def sample(self) -> Mapping[str, Any]:
        return {"pid":os.getpid(),"cwd":str(Path.cwd().resolve()),"python":os.sys.version.split()[0]}


@dataclass
class HttpJsonProbe(EnvironmentProbe):
    name: str
    url: str
    host_header: str | None = None
    timeout: float = 2.0
    def sample(self) -> Mapping[str, Any]:
        req=urllib.request.Request(self.url,headers={"Host":self.host_header} if self.host_header else {})
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r:
                parsed=json.loads(r.read())
                return {"reachable":True,"status":r.status,"body":parsed,"body_root":root(parsed)}
        except Exception as exc:
            return {"reachable":False,"error":type(exc).__name__+":"+str(exc)}


@dataclass
class RecursiveComputerProbe(EnvironmentProbe):
    name: str
    inspect_fn: Callable[[], Mapping[str, Any]]
    def sample(self) -> Mapping[str, Any]:
        state=dict(self.inspect_fn())
        return {"reachable":True,"state":state,"state_root":root(state)}


@dataclass
class AddressProbe(EnvironmentProbe):
    name: str
    resolve_fn: Callable[[], Mapping[str, Any]]
    def sample(self) -> Mapping[str, Any]:
        value=dict(self.resolve_fn())
        return {"resolved":True,"value":value,"value_root":root(value)}


class Observer2EnvironmentFederation:
    """Read-only composition of multiple existing BRAINK/KEX environment substrates."""
    def __init__(self, probes: list[EnvironmentProbe]):
        self.probes=list(probes)
    def sample(self) -> dict[str, Any]:
        env={}
        for probe in self.probes:
            if probe.name in env: raise ValueError("DUPLICATE_PROBE_NAME")
            env[probe.name]=dict(probe.sample())
        return {"environments":env,"environment_root":root(env)}
