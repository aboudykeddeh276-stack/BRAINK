# KEO Security and Privacy Boundary

## Default operating mode

```text
LOCAL_ONLY_NO_SOURCE_UPLOAD
```

The Community CLI reads and writes only paths explicitly supplied by the operator. It does not require an API key, network account, telemetry endpoint, remote model, or hosted source-code ingestion service.

## Current trust boundary

- The local operator controls the filesystem and execution environment.
- Generated JSON and Markdown files are ordinary local files.
- KEO does not execute generated target code automatically.
- KEO does not claim that a syntactically valid topology is secure, compiled, deployed, or physically executed.
- External connectors, CI systems, compilers, synthesizers, and deployment providers retain their own trust boundaries.

## Sensitive-data policy

Do not place credentials, private keys, access tokens, patient data, court-restricted evidence, or production secrets directly into KIR/topology files. Represent secret requirements by identity and provider reference, not plaintext value.

## Threat model for the current CLI

Relevant threats include:

- malicious or malformed project JSON;
- path confusion and accidental overwrite;
- topology identity collision;
- false promotion claims;
- untrusted generated source or templates;
- supply-chain compromise in later packaging or connectors;
- information disclosure through evidence exports.

## Current controls

- dependency-free runtime;
- explicit target directory;
- non-empty-directory refusal unless `--force` is supplied;
- schema-like structural validation;
- unique topology identity validation;
- strict local privacy declaration;
- explicit promotion and evidence states;
- Lovable exclusion;
- no implicit network operations.

## Required controls before Team or Enterprise release

```text
signed release artifacts
SBOM
reproducible build receipt
vulnerability scanning
secure update channel
role-based access control
audit event schema
secret-provider integration
tenant isolation
backup and recovery tests
threat-model review
penetration test
incident response procedure
security contact and disclosure process
```

## Vulnerability reporting

A public security contact and disclosure channel have not yet been established. This blocks a production-grade public release but does not block local alpha evaluation. Do not publish a security email address until the organisation has provisioned and monitors it.
