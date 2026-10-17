# KEDDEH MCP + SDK deployment surface

This package is a deployment surface of the resident KEDDEH/BRAINK fabric. It is not a separate hosted product and does not introduce an external deployment authority.

Canonical runtime:
- runtime://keddeh/mcp-sdk-environment
- environment://keddeh/mcp-sdk
- sdk://keddeh/braink

HTTP surfaces:
- /health
- /environment
- /sdk/manifest
- /sdk/docs
- /mcp

Deployment authority:
- KEDDEH Fabric / resident owner-host runtime
- GitHub self-hosted deployment runner
- Kubernetes deployment surface where the target host is the KEDDEH CloudWorkspace/Fabric cluster
- resident KEDDEH domain/publication fabric for external ingress

Promotion remains receipt-gated:

IMPLEMENTED
→ LOCAL_PASS
→ CI_PASS
→ TARGET_HOST_PASS
→ PROVIDER_PASS
→ DEPLOYED
→ EXTERNALLY_PROVEN

Required production secret:
- BRAINK_MCP_HMAC_KEY_HEX

Persistent state:
- BRAINK_MCP_STATE_DIR=/data/braink_mcp

No deployment claim is made until target-host start/readback and external ingress evidence are present.
