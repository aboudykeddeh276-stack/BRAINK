# Usage Notice

**Package:** `braink-runtime` 1.0.0 —
`KEDDEH_BRAINK_RUNTIME_PROOF_PACKAGE`
**Architect and originating author:** A. Keddeh

---

## 1. Ownership and governing licence

This package is part of the KEDDEH / BRAINK / KEX / KCORE body of work. It is
governed by the repository-level notices at the repository root:

* `KEDDEH_IP_LICENSE.md` — reservation of intellectual property rights.
* `LICENSE` — governance and redistribution scope.

Those documents take precedence. Nothing in this file grants any right they do
not grant. All intellectual property rights are reserved by A. Keddeh unless a
separate written agreement says otherwise. No clone, fork, pull request,
generated file, AI-agent contribution, automation run or execution of this
package transfers ownership, authorship or commercial rights.

## 2. Permitted use

Authorised tools, agents, collaborators and repositories may inspect, parse,
execute, test, adapt, document and improve this package for A. Keddeh-directed
development of the KEDDEH / BRAINK / KEX / KCORE system.

## 3. Restrictions

Without express written permission you may not claim authorship, relicense this
work, commercialise the doctrine, architecture, names or runtime concepts, remove
attribution, represent AI-agent elaboration as independent authorship, or extract
these methods into a competing proprietary system.

## 4. Warranty and proof disclaimer

This package is provided **as-is, without warranty of any kind**, express or
implied.

Read this carefully, because it is the whole point of the package:

* The evidence in `evidence/` records **local execution only**. Local proof from
  scripts, tests or manifests does **not** constitute external legal, scientific,
  operational or platform validation.
* **DNS:** authoritative external DNS confirmation is not possible from a
  sandbox. All DNS status is capped at `LOCALLY_EXECUTED`. No claim of
  `EXTERNALLY_OBSERVED` or `PUBLICLY_DEPLOYED` is made or implied.
* **Signing:** `TestSigner` uses a published, symmetric, **non-secret** key. It
  demonstrates a code path and provides **no authenticity, no confidentiality and
  no non-repudiation**. `ProductionSignerPlaceholder` is `DEFINED` only, holds no
  key and raises `NotImplementedError`; it cannot reach `PRODUCTION_VALIDATED`
  without real, independently attested key infrastructure.
* **Ledger:** the hash chain provides tamper *evidence*, not tamper
  *prevention*, and the root hash is not externally anchored.
* **Restart:** recovery is proven against a *simulated* unclean shutdown, not an
  OS-level kill or a power-loss event.

## 5. Security conditions of use

* No real secret, private key, token or production credential appears in this
  package, and none may be added to it — including to
  `config/signer.example.json`, `config/runtime.example.env` or any test.
* Production key material must be supplied at runtime through an environment
  variable or a secrets manager and must never be committed.
* Ledger payloads are stored in plaintext. Do not place sensitive data in them.
* This package is a proof harness. Do not deploy it as a production security,
  identity or DNS component.

## 6. Attribution

Attribution to A. Keddeh must be preserved in any permitted adaptation,
derivative, excerpt or reconstruction, including reconstructions produced by an
AI system from the prose in `docs/`.
