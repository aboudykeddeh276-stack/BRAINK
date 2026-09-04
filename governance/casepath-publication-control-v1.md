# CasePath Publication Control v1

This control contract turns CasePath publication into a verifiable transaction rather than a deployment assumption.

## Control boundary

`app://casepath` is the canonical identity. The public target is the exact Trust Centre route:

`https://casepath.com.au/your-data.html`

The required promotion marker is:

`How CasePath verifies what the platform does`

The R1 patch marker is:

`casepath-surface-function-verification-r1`

`PUBLIC_LIVE` is false unless every release predicate is independently satisfied.

## Transaction

```text
CP-PUB-001
  owner authority
      -> explicit owner-origin binding
      -> target preimage
CP-PUB-002
  additive mutation
      -> local postimage
      -> release consumption
CP-PUB-003
  exact target readback
      -> marker verification
      -> route regression
      -> proof-ledger agreement
      -> PUBLIC_LIVE
```

## Adapter model

The transaction controller is provider-neutral. A concrete executor may be:

- owner-host filesystem;
- SFTP/SSH;
- hosting control panel API;
- Git/CI deployment;
- Cloudflare Pages;
- static object hosting;
- another provider API.

The adapter is not allowed to establish ownership merely because it can reach a server. It must receive an explicit authoritative binding and return a release identifier plus evidence sufficient for postimage verification.

## Negative authority rules

The following are explicitly insufficient for production authority:

- DNS resolution;
- possession of the public URL;
- an internal Drive materialisation;
- a generated HTML copy;
- an unrelated GitHub repository;
- a ChatGPT Sites deployment.

## Promotion invariant

```text
PUBLIC_LIVE :=
  owner_origin_verified
  AND preimage_verified
  AND patch_executed
  AND postimage_verified
  AND owner_release_consumed
  AND exact_target_http_200
  AND required_marker_present
  AND patch_marker_present
  AND proof_ledger_agrees
```

Any unknown, missing, stale, contradictory or unverifiable predicate resolves to `false`.

## Engineering consequence

The current blocker is an external authority fact, not an architectural deficiency: the exact owner-controlled production origin and executable deployment mechanism must be explicitly bound before production mutation is attempted.

Once bound, the same transaction controller can route through whichever legitimate provider is actually authoritative without changing the proof model.
