---
title: "Development Handbook"
created_date: 2026-11-21
update_date: 2026-11-22
status: APPROVED
tags: [development-handbook, contributor-onboarding, coding-standards, agent-collaboration, documentation-navigation]
---

# Development Handbook

This is the starting point for building Koios Cold. It brings the coding philosophy, project-specific development boundaries, and agent workflow into the repository so a new contributor can work from durable instructions.

## Read First

| Reference | Responsibility |
| --- | --- |
| [Authoritative documentation](Authoritative/README.md) | Separates reusable engineering guidance from Koios-specific application and task records. |
| [Architecture index](Authoritative/Canon/Architecture/README.md) | Locates Craig Architecture and its coding, planning, AI-guidance, and local-contract supplements. |
| [Development profile](Authoritative/Identity/development_profile.md) | Applies the philosophy to Koios's simulation, presentation, source owners, and prototype boundaries. |
| [Source organization](Authoritative/Identity/source_organization.md) | Defines where Koios application responsibilities, local contracts, and tests should live. |
| [Agent workflow](Authoritative/Identity/agent_workflow.md) | Defines Craig, Lead Engineer, and Dot responsibilities, task intake, review, and handoff. |
| [Verification contract](Authoritative/Identity/verification_contract.md) | Distinguishes executable checks from future verification requirements. |
| [Local handbook contract](__ai__.md) | Defines this folder's maintenance and verification rules. |

## Documentation Boundaries

The handbook owns development practices. The established project families retain their subject ownership: `systems_architecture/` defines ship equipment; `game_design/` defines player interaction and consequences; `software_architecture/` defines application implementation; `lore/` defines fictional context; and `governance/` defines documentation authority, status, and lifecycle.

These paths identify source owners in the full project workspace. Their publication and task-time availability are covered by [Design Source Availability](Authoritative/Identity/development_profile.md#design-source-availability). The handbook does not reproduce their specifications.

GitHub Issues describe bounded intended work. PRs carry proposed changes and review. Neither replaces the governing source documents. Local `__ai__.md` files describe current folder contracts.

## Branch Workflow

`development` is the default branch and integration target for active work. Task branches originate there and open PRs back to it. `main` holds the latest stable release; a stable development state is promoted to `main` and tagged as a new release under [the agent workflow](Authoritative/Identity/agent_workflow.md#release-promotion).

## First Verification

From the repository root, with Git and a supported Node.js LTS installed:

```text
node docs/tools/check_docs.mjs
git diff --check
git diff --cached --check
```

These check documentation structure and whitespace. They do not prove game behavior or independent review. See the [verification contract](Authoritative/Identity/verification_contract.md) for interpretation and future checks.

## Adoption

The handbook is `APPROVED` within its stated scope and qualifications. New proposals retain their own status until adopted. Established game and engineering decisions keep their existing authority. Handbook approval does not resolve outstanding design questions or authorize deferred implementation.
