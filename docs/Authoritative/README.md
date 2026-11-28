---
title: "Authoritative Development Documentation"
created_date: 2026-11-21
update_date: 2026-11-21
status: APPROVED
tags: [development-authority, portable-guidance, project-bindings, approval-scope, source-ownership]
---

# Authoritative Development Documentation

This directory is the home for durable development rules. Each document's status and qualifications still apply: placement here does not approve a draft, implement software, or confer authority to perform an operation.

## Organization

- [Canon](Canon/README.md) defines portable architectural principles and coding guidance.
- [Identity](Identity/README.md) applies those principles to Koios's actual runtime boundaries and contributor roles.

Task plans describe intended work. Evidence records what was checked. Review evaluates the result. Owner decisions establish adoption and consequential scope. These have separate responsibilities.

## Ownership and Conflicts

Koios's established subject owners remain in their existing families, as identified by the [development profile](Identity/development_profile.md#design-source-availability). The handbook owns development practice, not a second definition of ship behavior or gameplay.

Read portable principles, the applicable Koios binding, and the nearest local contract before acting on a task. Project bindings may choose concrete tools and workflows without reversing the core dependency invariant. Task instructions can authorize bounded work; they do not silently rewrite durable policy.

When sources conflict, preserve the last adopted decision, identify the owning reference, and surface the conflict to the Lead Engineer or Craig. Keep proposed resolutions explicit. Runtime prompts, generated artifacts, GitHub permissions, and passing checks do not override their sources.
