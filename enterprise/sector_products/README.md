# BRAINK Sector Products

This directory is the canonical source for sector-specific product packages that share the same HR/BRAINK supervision, ingress, proof, continuation, and adapter contracts.

Each sector package is repository-ready and must preserve the same core product interface:

- register_service
- submit_work
- assign_agent_group
- supervise
- checkpoint
- handoff
- observe
- reconcile
- continue
- billable_receipt

Sector-specific differences belong in `functions.json`, `controls.json`, and `adapters.json`, not in the supervision mechanics.
