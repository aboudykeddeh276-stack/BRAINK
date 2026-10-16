# BRAINK User Workflow Interface Contract

## Purpose

The primary interface is designed around user outcomes rather than implementation mechanics.

The first-level workflow surfaces are:

1. AI interaction
2. Documents
3. Files
4. Legal work

The user should be able to complete ordinary work without knowing about KEX, IL-LLM, MCP, VFS, runtime hosts, carriers, ledgers, meshes, or deployment mechanics.

## Surface separation

### Primary

The home surface exposes only user-directed work:

- Ask BRAINK
- Documents
- Files
- Legal work

### Routine maintenance

Routine maintenance is not presented as a user task. The runtime is responsible for performing maintenance behind the workflow where the underlying capability permits it.

Maintenance status may affect the small status bar, but maintenance controls do not become primary navigation.

### Status

A compact status bar communicates only the minimum useful state:

- ready / working;
- attention when necessary;
- automatic saving/work persistence.

It is not a dashboard of infrastructure counters.

### Diagnostics

Diagnostics is a separate technical surface. It contains traces, audit information and learning/runtime inspection for users who need to troubleshoot the system.

Diagnostics does not become part of ordinary task completion.

### Administration

Administration is a separate privileged surface. It contains controls such as workspace rebinding, compatibility checks and native runtime controls.

Administrative controls are never presented as ordinary user workflow actions.

## Task-completion test

A workflow passes the interface contract when a person can:

- describe the desired outcome in ordinary language;
- find the relevant work area without understanding the implementation;
- bring documents/files into the workspace;
- start legal work from facts and source material;
- continue a task without being instructed to manage runtime plumbing;
- observe only useful status information unless they deliberately open Diagnostics or Administration.

The corresponding engineering test is intentionally negative as well as positive: internal operations must not leak back into the primary interface merely because they are technically interesting.

## Architectural relationship

The UI is a projection over the existing governed execution architecture. It does not replace the execution, VFS, provenance, evidence or authority layers.

The intended flow is:

user intent
→ workflow surface
→ semantic task resolution
→ existing governed capabilities
→ automated maintenance where required
→ artifact/result
→ concise status
→ optional evidence/diagnostics

This preserves the distinction between user experience and implementation substrate while allowing the substrate to remain substantially more sophisticated than the interface exposes.
