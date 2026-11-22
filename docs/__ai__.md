---
title: "Development Handbook Local Contract"
created_date: 2026-11-21
update_date: 2026-11-21
status: APPROVED
tags: [local-contract, handbook-maintenance, documentation-validation, source-boundaries, developer-tools]
---

# Development Handbook Local Contract

## Last Verified (CI)

No hosted CI is configured by this handbook. Local validation and the checked commit belong in the PR handoff. This section does not assert a CI pass or independent approval.

## Scope

- Folder: `docs/` and its descendants.
- Included: handbook Markdown, `tools/check_docs.mjs`, and its regression suite.
- Related entry point: root `AGENTS.md`, checked by the same validator.
- Excluded: other project families, archives, assets, credentials, and application runtime code.

## Purpose

Provide durable development guidance and a small, dependency-free checker for that guidance.

## Architectural Rules

- Canon owns reusable coding philosophy; Identity applies it to Koios.
- Preserve the established subject owners named by the development profile.
- `Authoritative/Identity/agent_workflow.md` owns the development/release branch policy; other handbook pages summarize it and link to that owner.
- Keep new policies proposed until adopted within their stated scope.
- Reconcile whole affected sections for current truth. Keep task history and check evidence in task/PR records.
- The checker is developer tooling; it must not import game code, inspect credentials, call the network, or traverse outside its supplied repository root.

## Allowed Dependencies

- Handbook: relative links to committed documentation and explicit path inventories for not-yet-published owners.
- Checker and regression suite: Node.js standard library only. The suite exercises the CLI in temporary fixtures.
- No dependency on another checkout, private chat history, provider SDK, or secret.

## Public API / Key Exports

- `node docs/tools/check_docs.mjs [repository-root]`: checks the handbook and root agent entry point; returns a nonzero exit code on failure.
- The root argument supports isolated verification fixtures. It defaults to the current working directory.

## File Index

- `README.md`: contributor navigation and handbook scope.
- `Authoritative/Canon/Architecture/`: reusable architectural guidance and supplements.
- `Authoritative/Identity/`: Koios development profile, role workflow, and check requirements.
- `tools/check_docs.mjs`: scoped metadata, heading, and repository-local link validation.
- `tools/tests/check_docs.test.mjs`: subprocess regression tests for the checker CLI.

## Known Gaps / Future-State Notes

- The existing design families may be available only in the full authoring workspace until separately published.
- Application dependency installation, Python quality gates, Godot checks, and hosted CI remain separate implementation tasks.
- This contract governs the initial handbook tree. Add narrower contracts when a distinct implementation concern warrants one.

## Cross-Folder Contracts

- Root `AGENTS.md` points here and to the authoritative read order without duplicating every policy.
- Existing design families own game requirements. This folder must not alter their engineering, gameplay, or fictional decisions.
- Task and PR records identify work-specific scope, actual verification, and review state.

## Verification Contract

```text
node docs/tools/check_docs.mjs
node --test docs/tools/tests/check_docs.test.mjs
git diff --check
git diff --cached --check
```

Reviewers also check scope, policy meaning, source ownership, and agreement between navigation and owning documents. A mechanical pass is not semantic approval.
