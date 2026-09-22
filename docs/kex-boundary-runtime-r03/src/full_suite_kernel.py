#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from distributed_runtime import ToTSafetyKernel,DistributedCoordinateDirectory,Layer2Reconciler
from layer1_9_reconciler import Layer1to9Reconciler
try:
 from kex_boundary import GeometryBoundaryAdapter
except Exception:
 GeometryBoundaryAdapter=None

@dataclass
class SuiteResult:
 coordinate:str
 generation:int
 directory_hash:str
 layer9_root:str
 consistent:bool
 evidence_root:str

class BRAINKSoftwareKernel:
 """Composition root for the currently executed R03 software surfaces."""
 def __init__(self,node_ids=('n1','n2','n3')):
  self.safety=ToTSafetyKernel();self.directory=DistributedCoordinateDirectory(node_ids,self.safety)
  self.layers=Layer1to9Reconciler();self.l2=Layer2Reconciler();self.geometry=GeometryBoundaryAdapter() if GeometryBoundaryAdapter else None
 def execute(self,coordinate,payload,proposer='n1',generation=1):
  self.safety.authorize('REGISTER',coordinate,payload,proposer=proposer)
  rec=self.directory.commit(coordinate,payload,proposer)
  p={1:{'bytes':len(payload)},2:{'proposer':proposer},3:{'coordinate':coordinate,'value_hash':rec.value_hash},4:{'geometry':'toroidal' if self.geometry else 'unavailable'},5:{'propagation':'local-model'},6:{'quorum':self.directory.quorum},7:{'execution':'python'},8:{'observation':'directory'},9:{'evidence_root_before':self.safety.root}}
  states=self.layers.reconcile_all(generation,p)
  reconciled=self.l2.reconcile(self.directory,coordinate)
  self.safety.authorize('OBSERVE',coordinate,states[-1].output_root,consistent=reconciled['consistent'])
  return SuiteResult(coordinate,rec.generation,rec.value_hash,states[-1].output_root,reconciled['consistent'],self.safety.root)
