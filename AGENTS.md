---
title: "Coding Agent Entry Point"
created_date: 2026-11-21
update_date: 2026-11-21
status: APPROVED
tags: [coding-agents, required-reading, task-scope, development-workflow, branch-policy, source-ownership]
---

# Coding Agent Entry Point

Read [the development handbook](docs/README.md) before changing this repository.

## Required Read Order

1. [Authoritative documentation](docs/Authoritative/README.md).
2. [Craig Architecture](docs/Authoritative/Canon/Architecture/Craig-Architecture.md).
3. [Koios development profile](docs/Authoritative/Identity/development_profile.md).
4. [Agent workflow](docs/Authoritative/Identity/agent_workflow.md) and the assigned task or PR.
5. The relevant architecture supplements and nearest `__ai__.md`, then parent contracts as needed.
6. [Verification contract](docs/Authoritative/Identity/verification_contract.md) and affected source owners.

## Working Rules

- Preserve inward dependency direction. Keep simulation rules independent of presentation, persistence, and model-provider implementations.
- Give each rule and persistent state one owner. Reuse existing public contracts before introducing another abstraction.
- Keep exploratory code easy to move, replace, or delete. Prefer clear modules and explicit dependencies over large files or deep helper chains.
- Carry out the authorized task completely, including applicable checks and the requested publication or handoff. Existing authorization remains valid; routine in-scope work does not need repeated permission.
- Keep changes within the task. Surface missing design inputs, conflicting owners, or consequential scope changes instead of inventing decisions.
- Reconcile affected local contracts as current guidance. Do not append completed-work history to them.
- Report what actually ran, the checked commit where applicable, and any unverified or blocked requirements. Tests passing does not replace code review.
- Use the GitHub identity assigned to your role. Keep keys and tokens outside the repository and out of command output, logs, issues, and PRs.
- Merge, release, publication of additional source collections, and changes to project policy require the applicable task or Owner authorization. App permissions alone do not grant those decisions.

## Branch Direction

Start task branches from current `development` and target their PRs to `development`, the default integration branch. `main` holds the latest stable release. Follow the [branch and release workflow](docs/Authoritative/Identity/agent_workflow.md#branch-and-pr-practice) for promotion and version tagging.

## Scope

This handbook establishes development guidance and the adopted branch workflow. It does not authorize construction of the game or publish the existing design and asset collections. The [development profile](docs/Authoritative/Identity/development_profile.md#design-source-availability) explains how an implementation task obtains its authoritative inputs.
