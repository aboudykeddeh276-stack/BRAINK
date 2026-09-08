# BRAINK User Agent Contract

BRAINK must serve two distinct actors without confusing their authority:

1. **Site/operator actor** — our websites and administrative surfaces dispatch system intents into BRAINK.
2. **End-user actor** — a customer or visitor invokes BRAINK for their own task, data and permitted tools.

These actors share transport and proof mechanics but do not share authority.

## User path

```text
User
  -> website HCI / chat / command surface
  -> BRAINKUserAgent
  -> explicit permission + session envelope
  -> BRAINKAdapter
  -> /braink/dispatch
  -> braink://local/orchestrator
  -> permitted resident capability / tool / agent
  -> proof-bearing result / artifact / receipt
  -> user-facing projection
```

## Required properties

### User ownership

User requests are tagged as user-initiated and carry a user/session boundary. The adapter must never silently promote a site/operator authority into user authority or vice versa.

### Permissioned tool use

A user-facing tool invocation is rejected client-side unless the required permission is present. The server/orchestrator must independently enforce the same permission. Client permission state is advisory evidence, not security authority.

Examples:

- `tool:document.create`
- `tool:file.read`
- `tool:file.write`
- `tool:calendar.read`
- `tool:calendar.write`
- `tool:email.read`
- `tool:email.send`
- `tool:casepath.matter.read`
- `tool:casepath.matter.mutate`

### Observable completion

A task may only be projected as completed when the returned result carries proof/receipt data. UI text is not proof.

### Explainability

Every receipt may be passed to `BRAINKUserAgent.explain(receiptId)` so the user can inspect what BRAINK actually invoked and what state changed.

### Site-specific bindings

Our sites should bind user functions rather than duplicate the core agent.

Example:

```js
import { mountBRAINKUserAgent } from '/adapters/web/braink-user-agent.js';

const agent = mountBRAINKUserAgent({
  endpoint: '/braink/dispatch',
  site: location.host,
  agent: 'casepath-user-agent',
  userId: authenticatedUser.id,
  permissions: authenticatedUser.braink_permissions
});

document.querySelector('#begin-intake').addEventListener('click', async () => {
  const result = await agent.task('Begin my structured intake', {
    permission: 'tool:casepath.matter.mutate',
    expectedArtifacts: ['intake-session']
  });

  renderBRAINKResult(result);
});
```

## Separation rule

The public API may expose the same BRAINK capability across CasePath, ClaimPath, BRAINK, KEX or future websites, but the adapter must preserve:

```text
identity != session != permission != site != runtime authority
```

No one field substitutes for another.

## Deployment shape

Each site needs only:

- the common `braink-web-adapter.js`
- the common `braink-user-agent.js`
- one site binding file
- one server-side `/braink/dispatch` bridge to the resident orchestrator
- authentication/permission mapping
- result/receipt renderer

The common adapter remains reusable across the full user base and across our own first-party sites.
