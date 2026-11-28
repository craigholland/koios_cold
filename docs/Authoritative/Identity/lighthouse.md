---
title: "Koios Lighthouse Project Configuration"
created_date: 2026-11-28
update_date: 2026-11-28
status: APPROVED
tags: [lighthouse, project-configuration, private-bindings, agent-workflow]
---

# Koios Lighthouse Project Configuration

The [portable project definition](../../../.lighthouse/project.toml) at the fixed
repository path `.lighthouse/project.toml` records public GitHub identities,
branches, labels and baseline verification. It defines Koios for Lighthouse,
not an instruction to start it. The [agent workflow](agent_workflow.md) still
owns development and release policy.

## Portable definition and private machine binding

The portable file is v1. The installation keeps an explicit private v2 binding
with the expected project/repository, separate implementation and review
workspaces, credential reference, approved integration commit and SHA-256 of the
exact tracked Git blob bytes. Consult the
[Lighthouse v2 binding schema](https://github.com/craigholland/lighthouse/blob/76b9bf5e4df490677fb3070fcd9494b58ca93342/docs/development/configuration.md#repository-definition-and-machine-binding)
rather than adding a Koios-specific loader or committing a private binding.
Machine paths, credential aliases and values, shared service safeguards, runtime
settings and per-run authorization remain outside Koios Git.

After independent review and Craig's merge, Lead verifies the exact merged
`development` commit and hashes its tracked definition blob, not a working copy
whose line endings may differ. Establish or refresh the trusted private pin
explicitly. Lighthouse checks that the pinned commit is an ancestor of or equal
to the selected integration base and that the base blob still matches. The
proposed file in a configuration-changing PR is review evidence only: that PR
is governed by the previously approved definition. This first adoption PR uses
the existing manual review process; it cannot approve its own new definition.

## Assisted workflow and verification

Craig manually relays a bounded Issue or exact same-PR revision to the existing
Dot. Dot implements in its isolated checkout using App `5869344`
(`craig-codex-dot[bot]`, numeric actor `359713928`). Codex reviews independently
using App `5869282` (numeric actor `359712317`); Craig decides and performs the
merge. Automatic Dot delivery remains deferred.

The portable baseline lists the handbook checker, its regressions, and
working/staged whitespace checks. These are not a substitute for the applicable
simulation or Godot checks in the [Koios verification contract](verification_contract.md).
They are verification declarations, not execution authority.

Koios integration remains inactive. Lead must verify the merged definition and
bring Craig a refreshed activation proposal; neither this file nor passing
offline checks authorizes activation, model or runner execution, merge or release.
Any future Lighthouse runner operation requires its own exact-run approval.
