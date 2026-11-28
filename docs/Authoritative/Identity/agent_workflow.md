---
title: "Koios Agent Development Workflow"
created_date: 2026-11-21
update_date: 2026-11-22
status: APPROVED
tags: [agent-workflow, github-identities, task-intake, code-review, handoff, owner-authority, development-integration, release-promotion, version-tags]
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
- Scope, non-goals, expected files, and existing owners to reuse. Identify intended placement and public surfaces using [source organization](source_organization.md) and the nearest local contracts.
- Repository, current branch, clean separation of task changes, and PR target.
- Available tools, runnable checks, and required evidence.
- Review owner, expected next action, and any delegated merge or external action.

Do not overwrite another contributor's work or stage unrelated files. Missing design sources are handled through the [development profile](development_profile.md#design-source-availability).

## Branch and PR Practice

| Branch | Purpose | Incoming work |
| --- | --- | --- |
| `development` | Default branch and integration surface for active development. | Reviewed task PRs. |
| Task branches | Bounded implementation, documentation, or repair work based on current `development`. | In-scope implementation slices; PRs target `development`. |
| `main` | Latest stable released state. | Authorized promotion of a stable `development` candidate. |

Use one task branch and one coherent PR into `development`. A descriptive name such as `codex/development-release-workflow` identifies bounded intent. Create nested Story/Epic branches only when a scoped plan establishes that ladder; their eventual integration target remains `development`.

Work in small implementation slices. Stage the task's explicit paths, inspect the staged diff, and keep the PR title and body aligned with the final change. Include related local contract updates and the checks needed for the changed scope.

Push task branches without rewriting shared history. Routine task work must not be pushed directly to `main`. If the remote head or base has moved, inspect the change and integrate it deliberately before making a readiness claim.

## Release Promotion

When `development` reaches a stable condition suitable for a release:

1. Identify the candidate commit, intended release scope, verification results, and any outstanding limitations for Craig's release decision.
2. Open a promotion PR from `development` to `main`. Review the complete release delta rather than treating a single task's checks as proof of the entire candidate.
3. Merge the promotion when Craig approves the release or explicitly delegates that exact operation. New development after the candidate was checked requires a freshness assessment before promotion.
4. Create the agreed version tag on the resulting released commit on `main`. Confirm that the tag resolves to that commit. Choose the version as part of the release decision; do not invent a version or tag an unapproved development head.

`development` remains the default branch after release. Keep its history reconciled with the release result before further integration when the chosen merge method creates a different history. No force push or release tag rewrite is implied by this workflow.

Establishing these branch roles does not itself declare a software release, create a tag, or authorize a promotion now. Release approval, merge execution, and tagging remain within their explicitly authorized scope.

## Review and Rework

The reviewer checks behavior, architecture, acceptance coverage, source ownership, relevant negative paths, and the immediate integration context. Check that file and folder placement supports discovery, modules remain cohesive, dependencies point inward, and affected local contracts describe the actual public surfaces. Automated checks are inputs to this judgment.

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
