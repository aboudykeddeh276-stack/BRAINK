class MarketValidator:
    def score(self,module):
        c=int(module.get("callable_functions",0)); t=float(module.get("test_pass_rate",0))
        p=1 if module.get("persistent_state") else 0; a=1 if module.get("audit_receipts") else 0
        b=1 if module.get("billable_unit") else 0; g=int(module.get("external_adapter_gaps",0))
        value=min(100,20*b+15*p+15*a+30*t+min(20,c*2))
        feasibility=max(0,min(100,40*t+20*p+20*a+20-max(0,g*3)))
        readiness=round((value+feasibility)/2,2)
        cls="MARKET_READY_CORE" if readiness>=80 and g==0 else ("PILOT_READY" if readiness>=65 else "ENGINEERING_REQUIRED")
        return {"value_score":round(value,2),"feasibility_score":round(feasibility,2),"readiness_score":readiness,"classification":cls}
