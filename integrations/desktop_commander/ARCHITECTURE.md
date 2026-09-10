# BRAINK Desktop Commander Host-Control Architecture

## Purpose
Desktop Commander is integrated as an execution carrier into the BRAINK/KEX host fabric. It does not replace BRAINK, KEX, IL-LLM, VFS, workbook state, resident runtimes, or host authority. It supplies a concrete MCP/remote bridge through which approved BRAINK host-control operations can reach Linux/macOS execution environments.

## Signal path
User / Site / Admin ingress
→ BRAINK request envelope
→ IL-LLM classification
→ KEX capability + authority resolution
→ HOST_CONTROL route
→ Desktop Commander carrier
→ resident host
→ process/filesystem/network/service mutation
→ readback
→ proof receipt
→ VFS/workbook/runtime state reconciliation.

## Identity separation
- BRAINK identity: system/orchestration identity.
- KEX authority: capability and execution permission.
- Host identity: actual execution substrate identity.
- Node identity: mesh/distributed runtime identity.
- Service identity: DNS, DA, registrar, mining, API, etc.
- Desktop Commander identity: transport/carrier identity only.

## Runtime classes
1. Local MCP mode: `npx -y @wonderwhy-er/desktop-commander@latest`
2. Remote device mode: `npx -y @wonderwhy-er/desktop-commander@latest remote`
3. Supervised host mode: the remote process is kept alive by systemd/launchd or BRAINK's resident supervisor.
4. App mode: NativeChatBot exposes host-control status and approved operations through the BRAINKDesktopCommanderPlugin surface.

## Online/offline behavior
ONLINE requires fresh host heartbeat and successful carrier readback. OFFLINE_LOCAL may retain cached local state and perform explicitly local-safe work, but external network mutations, DNS publication, registrar propagation, mining submission, and remote writes must queue or fail closed until ONLINE is revalidated.

## Proof law
No action is promoted to success from command dispatch alone. A successful host-control transaction requires: request_id, actor, capability, authority decision, host identity, command/action digest, execution result, readback result, timestamp, and proof root.
