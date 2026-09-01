# BRAINK Agent Runtime Fabric

This directory contains machine-readable agent/team process contracts and dispatchers for Keddeh Systems runtime/service work.

## Core fabric

`BRAINK_PUBLIC_SERVICE_AGENT_FABRIC.json` defines the shared agent teams and governed service processes. Its process law separates semantic state, execution state, evidence state, and projection state, and requires readback before promotion.

`BRAINK_PUBLIC_SERVICE_AGENT_ORCHESTRATOR.py` resolves a process contract and emits a hashed `STATE_DISPATCHED` receipt. A dispatch receipt is an assignment/provenance object, not proof that an external actuator ran.

## Keddeh mail service child team

`KEDDEH_MAIL_SERVICE_CHILD_TEAM_R1.json` is the dedicated child-team contract for the `keddeh.com` mail-service authority surface. It derives from the `personal:kex-domain-hosting-handoff` lineage and assigns the existing BRAINK/KEX agent roles rather than inventing a separate automation taxonomy.

The child team resolves:

1. mail/domain authority,
2. DNS/MX/SPF/DKIM/DMARC readback,
3. provider mailbox provisioning,
4. controlled send/receive verification,
5. security and least-privilege policy,
6. IL-LLM contextual translation and scoped capability lowering.

`KEDDEH_MAIL_SERVICE_CHILD_DISPATCHER.py` can dispatch one child-team process or all processes. Every receipt retains the input hash, assigned agents, process actions, promotion gate, and the explicit boundary `provider_mutation: NOT_CLAIMED` until an authenticated provider action and readback exist.

Example local dispatch:

```bash
printf '%s' '{"authority":"USER_AUTHORIZED_LIVE","domain":"keddeh.com"}' \
  | python runtime/agents/KEDDEH_MAIL_SERVICE_CHILD_DISPATCHER.py --all
```

## Promotion law

The mail service must not be promoted to `KEDDEH_MAIL_SERVICE_VERIFIED` until all of the following are evidenced:

- domain and system identity observed,
- MX route read back,
- provider mailbox read back,
- send and receive verified,
- security policy bound without exposing secrets,
- IL-LLM mail-context translation bound.

This directory intentionally keeps agent assignment separate from provider actuation. Agent process contracts can decide, classify, prepare and verify work; external Google Workspace/DNS mutations require a bound authenticated actuator and subsequent readback.
