# BRAINK Local Service V1 — Experimental

Status: `UNTESTED_IN_TARGET_HOST` until the test command below is executed on a checked-out workspace or CI runner.

This isolated slice proves one contract only:

`request -> context -> skill -> authorization -> tool -> evidence -> continuation -> response`

It deliberately does not replace `NativeChatBot`, accepted product runtime, or existing BRAINK architecture.

## Run tests

```bash
python3 -m unittest development.local_service_v1.tests.test_service -v
```

## Start API

```bash
python3 -m development.local_service_v1.server --host 127.0.0.1 --port 8765
```

Then POST JSON to `/v1/conversation/respond`:

```json
{"message":"diagnose runtime"}
```

Retrieve evidence with `GET /v1/trace/<transaction_id>`.

## Promotion gate

Do not promote this implementation on repository presence alone. Required evidence:

1. focused tests pass in an executable host;
2. unauthorized tool test proves no `tool_started` event occurs;
3. tool evidence exactly equals continuation evidence;
4. malformed input does not enter the ledger/inference path;
5. API smoke test demonstrates request and trace endpoints;
6. Change Review evaluates the resulting diff and execution evidence.
