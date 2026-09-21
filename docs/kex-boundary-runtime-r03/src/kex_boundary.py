#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass,field,asdict
from typing import List,Tuple
MAGIC=b'KEXB'; VERSION=1
class CodecError(ValueError): pass
def _varint(n:int)->bytes:
    if n<0: raise CodecError('negative count')
    o=bytearray()
    while True:
        b=n&127; n>>=7; o.append(b|(128 if n else 0))
        if not n:return bytes(o)
def _unvarint(b:bytes,i:int):
    n=0; shift=0
    for _ in range(10):
        if i>=len(b):raise CodecError('truncated varint')
        x=b[i];i+=1;n|=(x&127)<<shift
        if not x&128:return n,i
        shift+=7
    raise CodecError('varint overflow')
def encode_ab(bits:bytes)->bytes:
    if any(x not in (0,1) for x in bits):raise CodecError('input must contain only 0/1 bytes')
    runs=[];i=0
    while i<len(bits):
        v=bits[i];j=i+1
        while j<len(bits) and bits[j]==v:j+=1
        runs.append((v,j-i));i=j
    o=bytearray(MAGIC+bytes([VERSION]));o+=_varint(len(bits))+_varint(len(runs))
    for v,n in runs:o.append(65 if v else 66);o+=_varint(n)
    return bytes(o)
def decode_ab(blob:bytes)->bytes:
    if len(blob)<7 or blob[:4]!=MAGIC or blob[4]!=VERSION:raise CodecError('bad header')
    i=5;total,i=_unvarint(blob,i);nr,i=_unvarint(blob,i);out=bytearray();prev=None
    for _ in range(nr):
        if i>=len(blob):raise CodecError('truncated run symbol')
        s=blob[i];i+=1;n,i=_unvarint(blob,i)
        if s not in (65,66) or n==0:raise CodecError('invalid run')
        v=1 if s==65 else 0
        if prev==v:raise CodecError('non-canonical adjacent equal runs')
        out.extend(bytes([v])*n);prev=v
        if len(out)>total:raise CodecError('declared length exceeded')
    if len(out)!=total or i!=len(blob):raise CodecError('length/trailing-data mismatch')
    return bytes(out)
@dataclass(frozen=True)
class NodeDef:
    node_id:str;semantic_id:str;version:int;capability:str;inputs:Tuple[str,...];outputs:Tuple[str,...];attributes:Tuple[Tuple[str,str],...]
    def canonical(self):return json.dumps(self.__dict__,sort_keys=True,separators=(',',':')).encode()
    @property
    def definition_hash(self):return hashlib.sha256(self.canonical()).hexdigest()
@dataclass
class NodeInstance:
    instance_id:str;definition_hash:str;target:str;state:dict=field(default_factory=dict);observer:dict=field(default_factory=dict);integrations:List[str]=field(default_factory=list);attribution:List[dict]=field(default_factory=list)
class ToTSafetyKernel:
    allowed={'project':{'html','symbolic'},'encode':{'binary'},'decode':{'symbolic'},'observe':{'evidence'}}
    def __init__(self):self.history=[]
    def transition(self,node,action,payload):
        if action not in self.allowed:raise ValueError('ACTION_NOT_DECLARED')
        if node.capability not in {'dumb','smart'}:raise ValueError('CAPABILITY_INVALID')
        r={'action':action,'semantic_id':node.semantic_id,'payload':payload,'accepted':True};self.history.append(r);return r
class CoordinateDirectory:
    def __init__(self):self._m={}
    def register(self,coordinate,node_hash,epoch=1):
        if coordinate in self._m and self._m[coordinate]['node_hash']!=node_hash:raise ValueError('COORDINATE_CONFLICT')
        self._m[coordinate]={'node_hash':node_hash,'epoch':epoch}
    def resolve(self,coordinate):
        if coordinate not in self._m:raise KeyError('COORDINATE_UNRESOLVED')
        return dict(self._m[coordinate])
class Layer2Reconciler:
    def reconcile(self,expected,observations):
        a=[];r=[]
        for o in observations:
            if o.get('definition_hash')!=expected['definition_hash']:r.append((o,'DEFINITION_MISMATCH'))
            elif o.get('instance_id') is None:r.append((o,'INSTANCE_MISSING'))
            else:a.append(o)
        return {'accepted':a,'rejected':r,'consistent':not r}
def instantiate(node,target,instance_id):
    if not target or not instance_id:raise ValueError('INSTANCE_ID_AND_TARGET_REQUIRED')
    return NodeInstance(instance_id,node.definition_hash,target)
def project_html(node,inst):
    p={'node':node.node_id,'semantic_id':node.semantic_id,'definition_hash':node.definition_hash,'instance_id':inst.instance_id,'target':inst.target}
    return '<article data-kex-node="%s"><pre>%s</pre></article>'%(node.node_id,json.dumps(p,sort_keys=True))
def boundary_encode(bits):
    b=encode_ab(bits);return {'bytes':b,'sha256':hashlib.sha256(b).hexdigest(),'length':len(b)}
def boundary_decode(blob):
    b=decode_ab(blob);return {'bits':b,'sha256':hashlib.sha256(b).hexdigest(),'length':len(b)}


# Waveform Geometry Manifold adapter (R03-WG)
import math,zlib
TAU=2*math.pi
class GeometryViolation(RuntimeError): pass
@dataclass(frozen=True)
class GeometrySample:
    index:int;byte:int;theta:float;phi:float;x:float;y:float;z:float;norm:float;gaussian_curvature:float
@dataclass(frozen=True)
class WaveSymbol:
    index:int;amplitude:float;phase:float;frequency:float;sample_digest:str
@dataclass(frozen=True)
class GeometryFrame:
    generation:int;coordinate:str;payload_sha256:str;crc32:int;geometry_root:str;jitter_limit:float
def _gcanon(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
class WaveformGeometryEngine:
    def __init__(self,major_radius=10.0,minor_radius=3.0):
        if not major_radius>minor_radius>0:raise GeometryViolation('REQUIRE_R_GT_r_GT_0')
        self.R=float(major_radius);self.r=float(minor_radius)
    @property
    def norm_floor(self):return self.R-self.r
    def generate(self,data:bytes):
        n=max(1,len(data));out=[]
        for i,b in enumerate(data):
            theta=TAU*((i+0.5)/n)
            # 256 half-bin phase centres remove the original byte 0/255 endpoint alias at 0 == 2pi.
            phi=TAU*((b+0.5)/256.0)
            cp,sp,ct,st=math.cos(phi),math.sin(phi),math.cos(theta),math.sin(theta)
            x=(self.R+self.r*cp)*ct;y=(self.R+self.r*cp)*st;z=self.r*sp
            norm=math.sqrt(x*x+y*y+z*z)
            K=cp/(self.r*(self.R+self.r*cp))
            out.append(GeometrySample(i,b,theta,phi,x,y,z,norm,K))
        return tuple(out)
    def verify(self,samples,tol=1e-9):
        for s in samples:
            tube=(math.sqrt(s.x*s.x+s.y*s.y)-self.R)**2+s.z*s.z
            if abs(tube-self.r*self.r)>tol:raise GeometryViolation('TORUS_CONSTRAINT_VIOLATION')
            if s.norm<self.norm_floor-tol:raise GeometryViolation('NORM_FLOOR_VIOLATION')
        return True
class GeometricSignalModulator:
    def __init__(self,base_frequency=432.0):self.base=float(base_frequency)
    def modulate(self,samples):
        return tuple(WaveSymbol(s.index,s.norm,s.phi,self.base*(1+0.1*s.gaussian_curvature),hashlib.sha256(_gcanon(asdict(s))).hexdigest()) for s in samples)
class GeometricDemodulator:
    def demodulate(self,signal):
        out=bytearray()
        for w in signal:
            q=((w.phase%TAU)/TAU)*256.0-0.5
            out.append(int(round(q))%256)
        return bytes(out)
class GeometryBoundaryAdapter:
    def __init__(self,engine=None,jitter_limit=0.297):
        self.engine=engine or WaveformGeometryEngine();self.jitter_limit=float(jitter_limit);self.mod=GeometricSignalModulator();self.demod=GeometricDemodulator()
    def encode(self,data,coordinate,generation):
        if not coordinate or str(coordinate).strip().upper() in {'0','ZERO'}:raise GeometryViolation('ZERO_NOT_PERMITTED_AS_ADDRESS')
        if generation<=0:raise GeometryViolation('GENERATION_MUST_BE_POSITIVE')
        geom=self.engine.generate(data);self.engine.verify(geom);signal=self.mod.modulate(geom)
        root=hashlib.sha256(_gcanon([asdict(x) for x in geom])).hexdigest()
        frame=GeometryFrame(generation,coordinate,hashlib.sha256(data).hexdigest(),zlib.crc32(data)&0xffffffff,root,self.jitter_limit)
        return frame,signal,geom
    def decode(self,frame,signal,observed_jitter=0.0):
        if abs(observed_jitter)>frame.jitter_limit:raise GeometryViolation('JITTER_BOUND_EXCEEDED')
        data=self.demod.demodulate(signal)
        if hashlib.sha256(data).hexdigest()!=frame.payload_sha256 or (zlib.crc32(data)&0xffffffff)!=frame.crc32:raise GeometryViolation('PAYLOAD_INTEGRITY_FAILURE')
        return data
class WaveformCoordinateDirectory:
    def __init__(self):self.records={}
    def commit(self,frame):
        old=self.records.get(frame.coordinate)
        if old and frame.generation<=old.generation:raise GeometryViolation('STALE_OR_DUPLICATE_GENERATION')
        self.records[frame.coordinate]=frame
        return hashlib.sha256(_gcanon({k:asdict(v) for k,v in sorted(self.records.items())})).hexdigest()
class WaveformLayer2Reconciler:
    def reconcile(self,expected,observed):
        if observed is None:return 'MATERIALISE'
        if observed.coordinate!=expected.coordinate:raise GeometryViolation('COORDINATE_MISMATCH')
        if observed.generation>expected.generation:raise GeometryViolation('OBSERVED_GENERATION_AHEAD')
        if observed.generation<expected.generation or observed.payload_sha256!=expected.payload_sha256 or observed.geometry_root!=expected.geometry_root:return 'REPLACE'
        return 'NOOP'
