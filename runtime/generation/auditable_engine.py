"""KS-BRAINK-IL-LLM model-bound diffusion transaction with native ledger receipts.

Source architecture: A. Keddeh / KEDDEH Systems. No ephemeral neural weights.
A trained backbone and decoder must be explicitly supplied by the owner runtime.
"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable

import torch
from torch import Tensor, nn
from runtime.illlm_ledger import ILLLMImmutableLedger


def hash_tensor(tensor: Tensor) -> str:
    data = tensor.detach().cpu().contiguous().reshape(-1)
    body = str(data.dtype).encode() + b"|" + repr(tuple(data.shape)).encode() + b"|" + data.view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(body).hexdigest()


def hash_model(model: nn.Module) -> str:
    state = model.state_dict()
    if not state:
        raise ValueError("UNBOUND_MODEL_WEIGHTS")
    digest = hashlib.sha256()
    for key, value in sorted(state.items()):
        if not torch.isfinite(value).all():
            raise ValueError("NONFINITE_MODEL_WEIGHT")
        digest.update(key.encode()); digest.update(b"\0"); digest.update(hash_tensor(value).encode())
    return digest.hexdigest()


@dataclass(frozen=True)
class ExecutionProof:
    schema: str
    seed: int
    prediction_type: str
    scheduler_steps: int
    guidance_scale: float
    model_sha256: str
    decoder_sha256: str
    conditioning_sha256: str
    input_control_sha256: str | None
    negative_conditioning_sha256: str | None
    latent_sha256: str
    output_sha256: str
    step_sha256: tuple[str, ...]
    event_root: str
    event_id: str
    correlation_id: str
    environment: dict[str, str]


class AuditableGenerationEngine(nn.Module):
    """Denoise via owner's registered trained modules; append independently verifiable receipt.

    A model's constructor, checkpoint binding and authorisation precede this call.
    No claim of photorealism, deterministic GPU equivalence or learning promotion.
    """
    def __init__(self, *, backbone: nn.Module, decoder: nn.Module,
                 ledger: ILLLMImmutableLedger, device: str = "cpu",
                 dtype: torch.dtype = torch.float32, prediction_type: str = "v_prediction",
                 latent_scale: float = 1.0):
        super().__init__()
        if prediction_type not in {"v_prediction", "epsilon"}:
            raise ValueError("UNSUPPORTED_PREDICTION_PARAMETERIZATION")
        if not math.isfinite(latent_scale) or latent_scale <= 0:
            raise ValueError("INVALID_LATENT_SCALE")
        if dtype not in (torch.float32, torch.float16, torch.bfloat16):
            raise ValueError("UNSUPPORTED_DTYPE")
        self.device = torch.device(device)
        self.dtype = dtype
        if self.device.type == "cpu" and dtype != torch.float32:
            raise ValueError("CPU_ENGINE_REQUIRES_FLOAT32")
        self.backbone = backbone.to(device=self.device, dtype=self.dtype).eval()
        self.decoder = decoder.to(device=self.device, dtype=self.dtype).eval()
        self.prediction_type = prediction_type
        self.latent_scale = float(latent_scale)
        self.ledger = ledger
        self.model_sha256 = hash_model(self.backbone)
        self.decoder_sha256 = hash_model(self.decoder)

    @torch.inference_mode()
    def execute_transaction(self, *, conditioning_sequence: Tensor,
                            spatial_dimensions: tuple[int, int, int, int], seed: int,
                            scheduler_steps: int = 25, guidance_scale: float = 1.0,
                            structural_control: Tensor | None = None,
                            negative_conditioning_sequence: Tensor | None = None,
                            correlation_id: str) -> tuple[Tensor, ExecutionProof]:
        if not correlation_id or len(correlation_id) > 128:
            raise ValueError("CORRELATION_ID_REQUIRED")
        if type(seed) is not int or not (0 <= seed < 2**63):
            raise ValueError("INVALID_SEED")
        if type(scheduler_steps) is not int or not (1 <= scheduler_steps <= 200):
            raise ValueError("INVALID_STEP_BUDGET")
        if len(spatial_dimensions) != 4 or any(type(x) is not int or x <= 0 for x in spatial_dimensions):
            raise ValueError("INVALID_LATENT_SHAPE")
        if not math.isfinite(guidance_scale) or guidance_scale < 0 or guidance_scale > 25:
            raise ValueError("INVALID_GUIDANCE_SCALE")
        if guidance_scale != 1.0 and negative_conditioning_sequence is None:
            raise ValueError("CFG_REQUIRES_NEGATIVE_CONDITIONING")
        if conditioning_sequence.ndim != 3 or conditioning_sequence.shape[0] != spatial_dimensions[0]:
            raise ValueError("CONDITIONING_BATCH_OR_LAYOUT_MISMATCH")
        if negative_conditioning_sequence is not None and negative_conditioning_sequence.shape != conditioning_sequence.shape:
            raise ValueError("CFG_CONDITIONING_SHAPE_MISMATCH")
        condition = conditioning_sequence.to(device=self.device, dtype=self.dtype)
        negative = negative_conditioning_sequence.to(device=self.device, dtype=self.dtype) if negative_conditioning_sequence is not None else None
        control = structural_control.to(device=self.device, dtype=self.dtype) if structural_control is not None else None
        for t in [condition, negative, control]:
            if t is not None and not bool(torch.isfinite(t).all()):
                raise ValueError("NONFINITE_INPUT_TENSOR")
        if hash_model(self.backbone) != self.model_sha256 or hash_model(self.decoder) != self.decoder_sha256:
            raise ValueError("WEIGHTS_CHANGED_SINCE_BINDING")
        if self.ledger.verify().get("status") != "PASS":
            raise ValueError("ILLLM_LEDGER_UNVERIFIED")
        generator = torch.Generator(device=self.device).manual_seed(seed)
        latents = torch.randn(spatial_dimensions, generator=generator, device=self.device, dtype=self.dtype)
        betas = torch.linspace(0.00085, 0.0120, scheduler_steps, dtype=torch.float32, device=self.device)
        cumulative = torch.cumprod(1.0 - betas, dim=0)
        step_hashes: list[str] = []
        for step in range(scheduler_steps - 1, -1, -1):
            timestep = torch.tensor([step], dtype=torch.long, device=self.device)
            prediction = self.backbone(latents, timestep, condition, control)
            if guidance_scale != 1.0:
                base = self.backbone(latents, timestep, negative, control)
                prediction = base + guidance_scale * (prediction - base)
            if not isinstance(prediction, Tensor) or prediction.shape != latents.shape:
                raise ValueError("BACKBONE_PREDICTION_SHAPE_MISMATCH")
            if not bool(torch.isfinite(prediction).all()):
                raise ValueError("NONFINITE_BACKBONE_PREDICTION")
            alpha_bar = cumulative[step].to(dtype=self.dtype)
            if self.prediction_type == "v_prediction":
                prediction_noise = alpha_bar.sqrt() * prediction + (1.0-alpha_bar).sqrt() * latents
            else:
                prediction_noise = prediction
            prev_alpha = cumulative[step-1].to(dtype=self.dtype) if step > 0 else torch.tensor(1.0, device=self.device,dtype=self.dtype)
            predicted_x0 = (latents - (1.0-alpha_bar).sqrt()*prediction_noise) / alpha_bar.sqrt()
            latents = prev_alpha.sqrt()*predicted_x0 + (1.0-prev_alpha).sqrt()*prediction_noise
            if not bool(torch.isfinite(latents).all()):
                raise ValueError("NONFINITE_LATENT_STATE")
            step_hashes.append(hash_tensor(latents))
        output = self.decoder(latents / self.latent_scale)
        if not isinstance(output, Tensor) or output.ndim != 4 or output.shape[0] != spatial_dimensions[0]:
            raise ValueError("DECODER_LAYOUT_MISMATCH")
        if not bool(torch.isfinite(output).all()):
            raise ValueError("NONFINITE_DECODED_OUTPUT")
        if hash_model(self.backbone) != self.model_sha256 or hash_model(self.decoder) != self.decoder_sha256:
            raise ValueError("WEIGHTS_MUTATED_DURING_TRANSACTION")
        meta={"torch":torch.__version__,"device":str(self.device),"dtype":str(self.dtype),
              "cudnn":str(torch.backends.cudnn.version()) if self.device.type=='cuda' else "none"}
        payload={"seed":seed,"prediction_type":self.prediction_type,"scheduler_steps":scheduler_steps,
                 "guidance_scale":guidance_scale,"model_sha256":self.model_sha256,"decoder_sha256":self.decoder_sha256,
                 "conditioning_sha256":hash_tensor(condition),"input_control_sha256":hash_tensor(control) if control is not None else None,
                 "negative_conditioning_sha256":hash_tensor(negative) if negative is not None else None,
                 "latent_sha256":hash_tensor(latents),"output_sha256":hash_tensor(output),"step_sha256":step_hashes,
                 "environment":meta,"authority":"EXECUTED_WITH_REGISTERED_WEIGHTS_NOT_LEARNING_PROMOTED"}
        event=self.ledger.append(source_uri="braink://generation/diffusion/runtime",
                                 source_level="REGISTERED_MODEL_WEIGHT_EXECUTION",
                                 semantic_type="GENERATIVE_INFERENCE_RECEIPT",
                                 correlation_id=correlation_id,payload=payload,
                                 lexical_state={"conditioning_sha256":payload["conditioning_sha256"],
                                                "prediction_type":self.prediction_type},
                                 illlm_state={"model":self.model_sha256,"decoder":self.decoder_sha256,
                                              "output":payload["output_sha256"],"promotion":"NOT_PROMOTED"})
        return output, ExecutionProof("KS-BRAINK-IL-LLM/generation-proof/1",seed,self.prediction_type,
                 scheduler_steps,float(guidance_scale),self.model_sha256,self.decoder_sha256,
                 payload["conditioning_sha256"],payload["input_control_sha256"],
                 payload["negative_conditioning_sha256"],payload["latent_sha256"],
                 payload["output_sha256"],tuple(step_hashes),event.event_root,event.event_id,
                 correlation_id,meta)
