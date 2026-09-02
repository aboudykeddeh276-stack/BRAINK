from __future__ import annotations
from typing import Any, Dict
from .exposed_illlm import ExposedILLLM, root


class SectorResearchBridge:
    """Resolve exposed IL-LLM research before HR/BRAINK sector work dispatch."""

    def __init__(self, research: ExposedILLLM):
        self.research = research

    def prepare_function_context(self, product: str, function: str,
                                 controls: list[str], adapters: list[str]) -> Dict[str, Any]:
        function_packet = self.research.research_packet(function)
        control_packets = {control: self.research.research_packet(control) for control in controls}
        adapter_packets = {adapter: self.research.research_packet(adapter) for adapter in adapters}
        holes = []
        if function_packet.get("status") == "HOLE":
            holes.append({"type": "FUNCTION_RESEARCH_HOLE", "term": function})
        for control, packet in control_packets.items():
            if packet.get("status") == "HOLE":
                holes.append({"type": "CONTROL_RESEARCH_HOLE", "term": control})
        for adapter, packet in adapter_packets.items():
            if packet.get("status") == "HOLE":
                holes.append({"type": "ADAPTER_RESEARCH_HOLE", "term": adapter})
        context = {
            "product": product,
            "function": function,
            "function_research": function_packet,
            "control_research": control_packets,
            "adapter_research": adapter_packets,
            "research_holes": holes,
        }
        context["context_root"] = root(context)
        return context

    def work_module_payload(self, product: str, function: str,
                            controls: list[str], adapters: list[str]) -> Dict[str, Any]:
        context = self.prepare_function_context(product, function, controls, adapters)
        return {
            "work_module_id": "WM-RESEARCH-BOUND-" + context["context_root"][:16],
            "product": product,
            "function": function,
            "research_context_root": context["context_root"],
            "research_holes": context["research_holes"],
            "research_context": context,
        }
