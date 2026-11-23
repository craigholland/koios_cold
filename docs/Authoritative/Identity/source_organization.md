---
title: "Koios Source Organization"
created_date: 2026-11-22
update_date: 2026-11-23
status: APPROVED
tags: [source-organization, code-navigation, architectural-ownership, python, godot, local-contracts]
---

# Koios Source Organization

This standard owns concrete Koios source placement. It applies [Craig Architecture](../Canon/Architecture/Craig-Architecture.md) and the [development profile](development_profile.md) without changing either runtime's authority or replacing detailed design owners.

## Current and Planned Homes

The published handbook lives under `docs/`: `Authoritative/Canon/` holds reusable principles, `Authoritative/Identity/` binds them to Koios, and `tools/` contains handbook verification and its tests. Existing design families keep their roles and [availability rules](development_profile.md#design-source-availability).

The [headless simulation foundation](../../../simulation/README.md) uses a subset of the Python homes below. The local contract records what actually exists. Other examples are **planned**, not links or claims that code exists. Create a home only when an authorized slice needs it. Do not create empty layers, select a database engine, or select a bridge by adopting this layout.

## Python Simulation

Use `simulation/src/koios_sim/` for the Python package. Organize first by responsibility, then by capability using stable shared terms, such as `electrical` where that is the actual owner.

| Responsibility home | Responsibility |
| --- | --- |
| `domain/<capability>/` | Authoritative simulation concepts and state, deterministic rules and state transitions, and domain vocabulary and contracts. |
| `database/<capability>/` | Stored representations, mapping to and from domain types, and concrete repository implementations. Does not define simulation rules or own a second version of game state. |
| `services/<capability>/` | Application use-case coordination, command/query sequencing and transaction boundaries. Uses injected contracts without importing concrete persistence, transport, or provider code. |
| `interfaces/` | Outer delivery and bridge adapters translate requests, results and events at the Python boundary. Transport payloads are not domain types. |
| `composition/` | Outer startup and dependency wiring select concrete adapters and pass them explicitly. Not an application-service or domain dependency. |

A persistence contract belongs to its inward consumer: use the capability's domain contract for a domain operation, or a service-owned contract for an application-only need. The database implementation depends on that contract. Services call an implementation at runtime through injection, not by importing it. An in-memory implementation can satisfy the same seam where appropriate. Provider integrations that do not persist state live at an outer adapter boundary, not in `database/`.

## Godot Frontend

Use a separate planned `frontend/` Godot project. Choose the following responsibility homes as they become useful, then group scripts, scenes, and tests by capability or player surface.

| Planned home under `frontend/` | Responsibility |
| --- | --- |
| `app/` | Startup, scene composition, and top-level wiring. |
| `features/<surface>/` | Player-facing scenes and presentation behavior for one feature. |
| `components/` | Reusable controls and audiovisual components; no dependencies on private feature state. |
| `input/`, `movement/` | Direct controls and continuous movement/physics, kept responsive in Godot. |
| `state/`, `view_models/` | Transient UI/session state and projections of authoritative data. Projections do not own persistent simulation state. |
| `contracts/`, `bridge/` | Public frontend-facing command/query/event shapes and the adapter that communicates with Python; no transport selection here. |

The frontend can compose concepts from multiple Python capabilities. It need not mirror Python modules one-for-one. The source of persistent effects remains Python; Godot reports meaningful physical results through the agreed public boundary.

## Files, Contracts, and Verification

- Name files by one role and use the same capability vocabulary across layers when it aids discovery. Distinguish a domain model, a stored record, a service, and a view model rather than giving all four an ambiguous name.
- Use narrow, intentional public imports. Python can expose curated, side-effect-free package exports; Godot features consume named public contracts and reusable components rather than another feature's private scripts. Put translations at the boundary.
- Extract a focused module when a file mixes owners, hides dependencies, or forces readers to hold unrelated context. The [Python size guidance](../Canon/Architecture/Craig-Architecture-Python.md#cohesion-and-size) is a review heuristic, not a quota. Keep provisional structures easy to relocate.
- Put a concise `__ai__.md` beside durable source responsibilities. State purpose, ownership, allowed dependencies, important files, public surfaces, and checks that actually run. Use the [local contract standard](../Canon/Architecture/Craig-Architecture-__ai__-Template.md); use a parent contract until a narrower owner is warranted.
- Keep production packages separate from tests. Use `simulation/tests/` for headless checks and plan `frontend/tests/`; group by the applicable responsibility and capability as the suite grows. Verify the rules headlessly, orchestration with injected fakes, persistence through its adapter, presentation in Godot, and the bridge with bounded integration tests when configured. Keep repository-wide tooling and documentation outside runtime packages.

## Worked Navigation: Battery Status

This is a placement example, not a battery specification, implementation requirement, or API design. Start with the actual battery engineering document in `systems_architecture/` at the ref or workspace location supplied by the task. If the task changes player behavior, follow its `game_design/` requirements too. The [design-source availability rules](development_profile.md#design-source-availability) explain how to obtain these owners; they are not published by this standard.

1. Start at `simulation/src/koios_sim/domain/electrical/` for battery concepts, authoritative state and rules. An inward repository contract, if needed by this capability, belongs there.
2. Follow the shared capability name to `services/electrical/` for the battery-status query or command workflow, and `database/electrical/` for a stored record, mapping, and repository implementation if persistence is in scope. Concrete wiring belongs at `composition/`.
3. Follow the planned public command/query/event seam from Python's `interfaces/` to Godot's `frontend/contracts/` and `frontend/bridge/`. Find the display projection at `frontend/view_models/` and the player-facing panel under `frontend/features/`. Neither is a battery-state owner.
4. Read the nearest `__ai__.md` for the relevant scope, then locate the matching capability under `simulation/tests/domain/`, `simulation/tests/services/` or `simulation/tests/database/`, and the feature under `frontend/tests/`. A contract or test path is planned until a task creates it.
