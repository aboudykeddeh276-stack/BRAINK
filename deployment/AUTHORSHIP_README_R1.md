# AKD Authorship and Orphan Detection

Every AKD/KEDDEH service should carry application-level authorship metadata independently of Git commit metadata or hosting-provider identity.

Required classification states:

- `AKD_AUTHORED`: direct reference to the canonical AKD authorship root.
- `AKD_AUTHORED_INHERITED`: valid predecessor lineage to an AKD-authored service.
- `ORPHANED_AKD_SERVICE`: missing, broken, or conflicting authorship lineage.

Canonical files:

- `enterprise/governance/AKD_AUTHORSHIP_ROOT.json`
- `enterprise/governance/AUTHORSHIP_FIELD_CONTRACT.json`
- `enterprise/governance/authorship_guard.py`
- `deployment/AKD_AUTHORSHIP_POLICY.json`
- `scripts/kex-ci/test_authorship_guard.py`

Hosting, rebranding, replication, repo mirroring, or provider changes do not by themselves transfer authorship. Such changes must preserve the canonical authorship root and lineage fields.
