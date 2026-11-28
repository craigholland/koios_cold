---
title: "Craig Architecture Reference"
created_date: 2026-11-21
update_date: 2026-11-21
status: APPROVED
tags: [craig-architecture, coding-guidance, dependency-direction, planning, local-contracts]
---

# Craig Architecture Reference

Craig Architecture applies SOLID, Clean Architecture, and ports-and-adapters ideas to incremental, AI-assisted development. Start with the core philosophy, then read the supplements relevant to the work.

| Document | Responsibility |
| --- | --- |
| [Craig Architecture](Craig-Architecture.md) | Core invariants, responsibility placement, resource maturity, and evolutionary development. |
| [Planning and decomposition](Craig-Architecture-Planning-And-Decomposition.md) | Bounded tasks, reviewable changes, discovery, and code-shape planning. |
| [Python guidance](Craig-Architecture-Python.md) | Python package structure, models, contracts, wiring, and tests. |
| [AI contributor guidance](AI_Guidance/Craig-Architecture-AI-Guidance.md) | Orientation, execution, contract maintenance, and honest handoff. |
| [Local contract standard](Craig-Architecture-__ai__-Template.md) | Scope and content of folder-level `__ai__.md` files. |

The [Koios development profile](../../Identity/development_profile.md) applies these principles. The [agent workflow](../../Identity/agent_workflow.md) and [verification contract](../../Identity/verification_contract.md) select the project's initial operating practices.
