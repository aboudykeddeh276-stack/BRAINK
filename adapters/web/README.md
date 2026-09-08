# BRAINK Web Adapter

A thin integration surface that lets an existing website dispatch typed intents into BRAINK without making the website the owner of BRAINK state.

## Boundary

```text
Website / HCI
  -> BRAINK Web Adapter
  -> /braink/dispatch gateway
  -> braink://local/orchestrator
  -> resident capability / runtime / tool
  -> proof-bearing result
  -> Website / HCI projection
```

The adapter is not a replacement runtime. It is a translation, transport, capability and proof boundary.

## Drop-in usage

```html
<script type="module">
  import { mountBRAINK } from '/adapters/web/braink-web-adapter.js';

  const braink = mountBRAINK({
    endpoint: '/braink/dispatch',
    site: location.host,
    agent: 'casepath-web'
  });

  const result = await braink.dispatch('casepath.intake.begin', {
    matter_id: 'example-123'
  });

  console.log(result.output, result.proof);
</script>
```

## Local website capability

A site may expose a narrow capability to BRAINK without transferring authority over BRAINK state:

```js
const remove = braink.registerCapability('ui.panel.open', async ({ panel }) => {
  document.querySelector(`[data-panel="${panel}"]`)?.removeAttribute('hidden');
  return { opened: panel };
});
```

## Protocol v1 request

```json
{
  "protocol": "braink.adapter.v1",
  "kind": "intent",
  "correlation_id": "uuid",
  "site": "casepath.com.au",
  "agent": "casepath-web",
  "intent": "casepath.intake.begin",
  "payload": {},
  "requested_capabilities": [],
  "proof_required": true,
  "issued_at": "ISO-8601"
}
```

## Protocol v1 result

A successful result must be correlated and proof-bearing:

```json
{
  "protocol": "braink.adapter.v1",
  "kind": "result",
  "correlation_id": "uuid",
  "route": "braink://local/orchestrator/casepath.intake.begin",
  "status": "completed",
  "output": {},
  "proof": {
    "source": "runtime-receipt",
    "observed": true,
    "receipt_id": "..."
  }
}
```

The adapter rejects a claimed `completed` result when proof is absent.

## Browser events

The adapter projects lifecycle events onto `window`:

- `braink:adapter:ready`
- `braink:dispatch:start`
- `braink:dispatch:complete`
- `braink:dispatch:error`

These are projection events only. They are not BRAINK's authoritative state ledger.

## Integration rule

Each website gets a small site-specific binding module containing its allowed intents and UI mappings. The common adapter remains identical across CasePath, ClaimPath, BRAINK sites, KEX surfaces and future carriers.
