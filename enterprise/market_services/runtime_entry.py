from __future__ import annotations
import argparse, json, os
from pathlib import Path
from .service_broker import MarketServiceBroker

DEFAULT_STATE = Path(os.getenv("BRAINK_MARKET_STATE", "./runtime_state/market_service_broker.sqlite3"))

def main():
    ap=argparse.ArgumentParser(description="BRAINK market-service runtime entry")
    ap.add_argument("service")
    ap.add_argument("function")
    ap.add_argument("--payload",default="{}",help="JSON payload")
    ap.add_argument("--customer",default="customer://local")
    ap.add_argument("--scope",default="SERVICE")
    ap.add_argument("--state",default=str(DEFAULT_STATE))
    args=ap.parse_args()
    state=Path(args.state)
    state.parent.mkdir(parents=True,exist_ok=True)
    broker=MarketServiceBroker(state)
    result=broker.execute(args.service,args.function,json.loads(args.payload),customer_id=args.customer,authority_scope=args.scope)
    print(json.dumps(result,indent=2))
    return 0 if result["status"] in {"PASS","REJECTED"} else 2

if __name__ == "__main__":
    raise SystemExit(main())
