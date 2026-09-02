class StateReconciler:
    def reconcile(self,declared,observed):
        deltas=[]
        for k in sorted(set(declared)|set(observed)):
            d=declared.get(k,"__ABSENT__"); o=observed.get(k,"__ABSENT__")
            if d!=o:
                c="MISSING_OBSERVATION" if o=="__ABSENT__" else ("UNDECLARED_OBSERVATION" if d=="__ABSENT__" else "STATE_DRIFT")
                deltas.append({"key":k,"declared":d,"observed":o,"class":c})
        return {"status":"RECONCILED" if not deltas else "DELTA_FOUND","deltas":deltas,
                "repair_obligations":[{"type":"RECONCILE_STATE","key":x["key"],"class":x["class"]} for x in deltas]}
