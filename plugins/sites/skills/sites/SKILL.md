---
name: sites
description: Build, edit, version, deploy, verify, recover, and continue owner-controlled website projects through @Sites.
---

# @Sites

Use the @Sites MCP server as the authoritative execution surface for website work.

For existing work, call `sites_list` and `site_get` before creating anything. Preserve the persistent Site identity, historical lineage, domains, versions, deployments, and receipts.

For a modification: inspect -> create immutable source version -> deploy through the intended adapter -> perform public readback -> verify ledger. Do not describe a planned change as completed.

Never infer that a GitHub repository backs a Site merely because names match. Never treat a domain binding as DNS/TLS success. Never treat a successful deployment command as public availability. Preserve contradictory historical evidence rather than silently reconciling it.

Use `estate_import` only to rehydrate recovered historical identities. Historical PASS is not current-live PASS.

When a required provider adapter is unavailable, return the exact blocked capability rather than substituting another hosting provider.
