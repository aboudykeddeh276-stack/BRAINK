from __future__ import annotations
from typing import Dict,Any

def rank_sectors(registry:Dict[str,Any]):
    ranked=[]
    for sector,cfg in registry["sectors"].items():
        score=3.0/cfg["priority"] + 0.12*len(cfg["market_functions"]) + 0.08*len(cfg["product_vectors"])
        ranked.append({"sector":sector,"score":score,"function_count":len(cfg["market_functions"]),
                       "product_vectors":cfg["product_vectors"]})
    return sorted(ranked,key=lambda x:(-x["score"],x["sector"]))
