"""CPU protocol tests only; not a generative-model quality claim."""
import pytest
import torch
from torch import nn
from runtime.illlm_ledger import ILLLMImmutableLedger
from runtime.generation.auditable_engine import AuditableGenerationEngine, hash_tensor

class TrainedWeightsContractBackbone(nn.Module):
    def __init__(self):
        super().__init__();self.conv=nn.Conv2d(2,2,1)
    def forward(self,latents,timestep,conditioning,control):
        # Test a REAL torch operator with explicitly registered weights.
        return self.conv(latents)+conditioning.mean()*0.01
class RegisteredDecoder(nn.Module):
    def __init__(self):
        super().__init__();self.conv=nn.Conv2d(2,3,1)
    def forward(self,latents):return torch.sigmoid(self.conv(latents))

def engine(tmp_path):
    torch.manual_seed(17)
    return AuditableGenerationEngine(backbone=TrainedWeightsContractBackbone(),decoder=RegisteredDecoder(),
              ledger=ILLLMImmutableLedger(tmp_path/"generation.jsonl"),prediction_type="v_prediction",device="cpu")

def test_cpu_computes_persisted_weight_bound_proof(tmp_path):
    e=engine(tmp_path);cond=torch.ones(1,3,4)
    result,proof=e.execute_transaction(conditioning_sequence=cond,spatial_dimensions=(1,2,4,4),seed=47,scheduler_steps=3,correlation_id="learn/gen/proof-001")
    assert result.shape==(1,3,4,4)
    assert proof.output_sha256==hash_tensor(result)
    assert len(proof.step_sha256)==3
    r=e.ledger.verify();assert r["events"]==1 and r["head"]==proof.event_root
    assert e.ledger.read_by_correlation("learn/gen/proof-001")[0]["payload"]["model_sha256"]==proof.model_sha256
    result2,proof2=e.execute_transaction(conditioning_sequence=cond,spatial_dimensions=(1,2,4,4),seed=47,scheduler_steps=3,correlation_id="learn/gen/proof-002")
    assert proof.output_sha256==proof2.output_sha256
    assert proof.model_sha256==proof2.model_sha256

def test_guidance_and_weight_mutation_fail_closed(tmp_path):
    e=engine(tmp_path);cond=torch.ones(1,3,4)
    with pytest.raises(ValueError,match="CFG_REQUIRES_NEGATIVE_CONDITIONING"):
        e.execute_transaction(conditioning_sequence=cond,spatial_dimensions=(1,2,4,4),seed=47,scheduler_steps=2,guidance_scale=7.5,correlation_id="bad-1")
    with torch.no_grad():e.backbone.conv.weight.add_(1.0)
    with pytest.raises(ValueError,match="WEIGHTS_CHANGED_SINCE_BINDING"):
        e.execute_transaction(conditioning_sequence=cond,spatial_dimensions=(1,2,4,4),seed=47,scheduler_steps=2,correlation_id="bad-2")
    assert e.ledger.verify()["events"]==0

def test_unregistered_weights_rejected(tmp_path):
    with pytest.raises(ValueError,match="UNBOUND_MODEL_WEIGHTS"):
        AuditableGenerationEngine(backbone=nn.Identity(),decoder=RegisteredDecoder(),ledger=ILLLMImmutableLedger(tmp_path/"g.jsonl"))
