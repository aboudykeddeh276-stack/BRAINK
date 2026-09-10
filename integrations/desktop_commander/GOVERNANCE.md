# BRAINK Desktop Commander Governance

Desktop Commander is an execution carrier. It never grants authority merely because it can reach a host.

Required decision order:
1. Resolve actor and ingress class: user, site, admin, agent, scheduled runtime.
2. Resolve requested capability.
3. Resolve authority and scope.
4. Resolve target host/node/service.
5. Dispatch only through an approved HOST_CONTROL route.
6. Capture command/action digest before execution.
7. Execute.
8. Read back observable state.
9. Commit receipt/proof.
10. Promote state only from observed result.

Denied by default:
- arbitrary privilege escalation;
- unrestricted root shell exposure to front-end/site users;
- repository-stored secrets or remote credentials;
- destructive filesystem/network mutations without an explicit capability;
- treating process launch as proof that the service is healthy;
- treating carrier connection as host identity;
- treating stale heartbeat as connected;
- flushing queued offline network mutations without revalidation.

Capability tiers:
- OBSERVE: status, process list, filesystem metadata, route/service health.
- OPERATE: start/stop/restart approved services, run approved diagnostics.
- MUTATE: bounded configuration/file changes with readback and rollback material.
- ADMIN: infrastructure authority changes, explicitly scoped and proof-gated.

Network/ISP rule:
The host-control carrier may configure and inspect DNS, DA, registrar, TCP, mesh, routing and BGP runtimes. It does not create public ASN/prefix authority, registry authority, transit contracts or upstream peering by itself. Those external authorities remain separately bound and readback-gated.

Mining rule:
A host carrier may launch and supervise Stratum/hash runtimes. A local candidate is not an accepted share. Only a correlated pool response may promote SUBMITTED to ACCEPTED or REJECTED.
