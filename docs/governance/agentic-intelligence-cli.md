# BRAINK/KEX Agentic Intelligence CLI Start

## Purpose

This document starts the automated agentic tool, intelligence software tool, and programmer route for BRAINK/KEX repositories.

The first executable artifact is `scripts/braink-agent-cli.py`.

## Function

`FUNCTION_INVENTORY_REPOSITORIES_AND_PLAN_AGENTIC_PROGRAMMER_INPUTS`

The CLI scans local git repositories, records branch/head/dirty state, checks governance baseline readiness, and emits a deterministic JSON plan for building a CLI, agent, and augmented-intelligence software layer from repositories available in the local environment.

## Commands

```bash
./scripts/braink-agent-cli.py status
./scripts/braink-agent-cli.py scan --repo-root ..
```

## Boundary

- The CLI does not execute arbitrary code from discovered repositories.
- The CLI only proves local repository discovery and local artifact classification.
- Repositories not present in the filesystem remain `PENDING_EXTERNAL_REPOSITORY_ACCESS_FOR_REPOS_NOT_PRESENT_LOCALLY`.
- Remote fetch, push, and cross-repository adoption remain pending until authenticated access is provided and each repository passes its own checker.

## Next build gates

1. Add repository adapters for known a.keddeh repositories.
2. Add a command runner with allowlisted commands only.
3. Add a planner that converts repository signals into task packets.
4. Add a local evidence ledger for agent actions and proof outputs.
