---
title: "Koios Agent Development Workflow"
created_date: 2026-11-21
update_date: 2026-11-21
status: DRAFT
tags: [agent-workflow, github-identities, task-intake, code-review, handoff, owner-authority, merge-scope]
---

# Koios Agent Development Workflow

Use durable task scope, bounded implementation, and reviewable handoffs. [Craig Architecture planning guidance](../Canon/Architecture/Craig-Architecture-Planning-And-Decomposition.md) defines decomposition; this document binds the initial Koios contributor workflow.

## Responsibilities and Identities

| Actor | GitHub identity | Responsibility |
| --- | --- | --- |
| Craig | `craigholland` | Project owner and game director; adopts scope, resolves consequential design decisions, and controls release and policy decisions. |
| Lead Engineer | `codex-lead-engineer[bot]` | Translates authorized objectives into bounded work, maintains engineering coherence, reviews implementations, and coordinates findings and handoffs. |
| Dot | `craig-codex-dot[bot]` | Implements assigned work, runs applicable checks, publishes scoped branches/PRs, and addresses review findings. |

The initial workflow separates Dot's implementation from Lead Engineer review. If the Lead implements a change, its own checks are author verification rather than independent approval. Craig can review it or name an independent reviewer.

## Authority and Authentication

Use the App credentials associated with the active role. App installation authentication provides separate bot attribution. The shared connector or an existing CLI login may act as Craig; do not silently use that identity for agent work.

Keep App private keys outside the repository. Generate short-lived credentials only in the execution environment that needs them, scope them to the assigned repository and required permissions, and keep them out of logs and delivery artifacts. Authentication setup does not itself grant implementation or merge authority.

Workers publish work for review. Dot does not merge, approve its own work, change policy, or perform releases unless Craig explicitly delegates a particular action. Lead review may recommend acceptance; merge execution follows the applicable user instruction or task policy. Opening a PR does not authorize merging it.

Craig's existing authorization persists for necessary in-scope operations. Do not request the same permission repeatedly. If a new consequential decision or a genuine source conflict is required, name the issue and continue useful independent work.

## Task Intake

Read root `AGENTS.md`, the handbook's required sources, the assigned issue or work packet, and affected local contracts. Confirm:

- Objective, actual authoritative requirements, and acceptance criteria.
- Scope, non-goals, expected files, and existing owners to reuse.
- Repository, current branch, clean separation of task changes, and PR target.
- Available tools, runnable checks, and required evidence.
- Review owner, expected next action, and any delegated merge or external action.

Do not overwrite another contributor's work or stage unrelated files. Missing design sources are handled through the [development profile](development_profile.md#design-source-availability).

## Branch and PR Practice

Initially, use one task branch and one coherent PR into the agreed base branch, normally `main`. A descriptive name such as `codex/docs-development-handbook` identifies bounded intent. Create nested Story/Epic branches only when a scoped plan establishes that ladder.

Work in small implementation slices. Stage the task's explicit paths, inspect the staged diff, and keep the PR title and body aligned with the final change. Include related local contract updates and the checks needed for the changed scope.

Push without rewriting shared history. If the remote head or base has moved, inspect the change and integrate it deliberately before making a readiness claim.

## Review and Rework

The reviewer checks behavior, architecture, acceptance coverage, source ownership, relevant negative paths, and the immediate integration context. Automated checks are inputs to this judgment.

Record findings with a concrete consequence and affected surface. The implementer repairs in-scope findings or gives a visible, evidence-based disposition. Refresh affected checks and review when implementation or requirements change. Consequential design changes return to Craig rather than becoming review-time invention.

Only the applicable authorized actor merges. Changes proposed by the Lead Engineer remain subject to review; its App's technical ability to merge is not self-approval.

## Handoff Record

Use the issue or PR to leave:

1. Objective and resulting behavior or documentation.
2. Changed files and relevant source references.
3. PR, base, and current head SHA.
4. Exact checks, working directory, checked SHA, results, and skips or blockers.
5. Unresolved findings or decisions and the actor responsible for them.
6. Next actor and expected action.

Record evidence proportionately. A concise PR body is sufficient for this documentation bootstrap. More elaborate machine-readable packets need an explicit project contract before becoming required.

## Durable Context and Quiet Coordination

Use authoritative documents for lasting rules, issues for bounded work, PRs for proposed changes and review, and local contracts for current folder expectations. Keep task status out of architectural specifications.

A handoff transfers a named action; routine status does not. Monitoring another actor or posting recurring updates requires an assigned coordination task. Report meaningful movement, required input, or a blocker without generating idle comments.
