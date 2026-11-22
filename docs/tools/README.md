---
title: "Handbook Validation Tool"
created_date: 2026-11-21
update_date: 2026-11-21
status: APPROVED
tags: [documentation-tooling, markdown-links, heading-validation, metadata-validation, local-checks]
---

# Handbook Validation Tool

Run `node docs/tools/check_docs.mjs` from the repository root. An optional repository-root argument supports isolated fixtures. The process returns nonzero when validation fails.

Run `node --test docs/tools/tests/check_docs.test.mjs` from the repository root to exercise the CLI against disposable fixtures. The tests use Node built-ins only, with no dependency installation or network access.

The tool checks `docs/**/*.md` and root `AGENTS.md` with Node's standard library. It does not access the network or external source collections. [The verification contract](../Authoritative/Identity/verification_contract.md) defines the checks' scope and limits; [the local contract](../__ai__.md) governs maintenance.

Use ordinary inline Markdown links and ATX headings in the handbook. Fenced examples are excluded from heading/link checks. The validator handles automatic duplicate-heading suffixes and explicit HTML `id`/`name` anchors. It is a scoped handbook checker, not a complete Markdown renderer or a general repository audit.
