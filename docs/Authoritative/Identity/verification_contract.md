---
title: "Koios Development Verification Contract"
created_date: 2026-11-21
update_date: 2026-11-23
status: APPROVED
tags: [documentation-validation, executable-checks, verification-evidence, test-readiness, final-head-freshness]
---

# Koios Development Verification Contract

This document owns runnable development checks and their evidence expectations. Game Design acceptance requirements and Software Architecture's fixture specifications remain with their source owners. A written test requirement is not an executed test.

## Available Handbook Checks

Prerequisites: Git and a supported Node.js LTS. The checker uses only Node's standard library and needs no dependency installation.

Run from the repository root:

```text
node docs/tools/check_docs.mjs
node --test docs/tools/tests/check_docs.test.mjs
git diff --check
git diff --cached --check
```

The checker covers Markdown under `docs/` and root `AGENTS.md`. It checks front matter, date/status/tag fields, heading hierarchy, explicit-anchor collisions, and repository-local link targets, exact path-component casing, and fragments. It ignores fenced examples and excludes same-line inline code spans from link checks. It does not fetch external URLs, inspect design collections, or evaluate engineering and gameplay meaning.

The regression suite runs the checker CLI against test-owned temporary handbook fixtures and checks both success and failure diagnostics. It does not change the repository handbook. Whitespace checks apply to unstaged and staged tracked changes respectively. Inspect `git status --short` and the explicit file inventory as well: a clean diff command does not prove that untracked files were reviewed or included.

## Semantic Documentation Review

Review scope and accuracy in addition to mechanical checks:

- Each detailed rule has a clear owner and cross-references remain navigable.
- Canon stays portable and Identity contains the actual Koios choices.
- Documents distinguish accepted requirements, draft policies, unresolved inputs, and implemented behavior.
- Local contracts describe current responsibilities rather than a progress log. From the task entry point, a contributor can trace the affected concept to its owner, public surface, and tests; review cohesion, placement, and inward dependencies against [source organization](source_organization.md).
- Agent roles, actual authentication, technical permissions, and delegated authority remain distinct.
- Task PRs target `development`; release promotion and tags follow the owning agent workflow.
- A fresh contributor can locate the actual design sources required by the task.

## Application Verification Readiness

The installable headless Python M0 foundation has a developer status query, an Operations replay and a
Ruff, mypy, and pytest baseline. Follow the [simulation setup and checks](../../../simulation/README.md#windows-setup-and-verification)
from a clean environment. These checks exercise deterministic Operations, not real physical movement,
Godot, inference, or persistence. This handbook does not create hosted application CI.

Godot presentation and continuous physics need their own scoped verification. A headless simulation pass does not establish rendering, control responsiveness, sound quality, or end-to-end bridge correctness. Inference behavior and provider availability need separately scoped checks and authored fallback coverage when implemented.

Do not present proposed baseline commands as runnable until their configuration exists. Do not run deferred builds or fixtures merely because another document describes them.

## Evidence and Freshness

For a PR, report the exact commands, cwd, results, checked commit, current head, base branch, and meaningful limitations. Keep secrets and live private payloads out of transcripts. A blocked or skipped check remains blocked or skipped.

Task verification covers the change against its `development` base. A release candidate needs verification appropriate to the complete promoted state and an exact commit record under [Release Promotion](agent_workflow.md#release-promotion). A task check or the existence of a version tag alone does not establish release readiness.

If the branch changes after checking, inspect the intervening paths and determine which checks and review need refreshing. Verify the remote PR head after push. Hosted CI that does not exist or did not run cannot be claimed as passing.

Checks support author handoff and independent review. They do not themselves approve a PR, authorize a merge, adopt new design rules, or authorize a release.
