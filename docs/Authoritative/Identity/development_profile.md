---
title: "Koios Development Profile"
created_date: 2026-11-21
update_date: 2026-11-22
status: APPROVED
tags: [koios-runtime, python-simulation, godot-presentation, authoritative-state, prototype-boundaries, source-availability]
---

# Koios Development Profile

Apply [Craig Architecture](../Canon/Architecture/Craig-Architecture.md) to a game whose ship, equipment, resource use, and recovery must work coherently. This document owns the coding application of that philosophy. Detailed runtime and equipment specifications retain their established owners.

## Runtime Boundaries

The established implementation direction uses a headlessly executable Python semantic simulation and Godot presentation/continuous physics, connected through explicit commands, queries, and events.

Python owns authoritative persistent state and semantic transitions: service dependencies, energy, equipment condition, inventory, permissions, time-dependent outcomes, and mission predicates within the implemented scope.

Godot owns presentation, direct input, continuous movement/physics, audio, and reporting meaningful physical results to the semantic simulation. Keep responsive movement local to that layer while reconciling persistent consequences through the authoritative model.

Ellie's integration consumes available evidence and constrained application interfaces. Generated language cannot invent world facts, acquire unavailable knowledge, or bypass simulation-owned authority and state transitions.

Exact bridge technology, shipping integration, schemas, and performance limits remain with `software_architecture/` and the authorized implementation task. This profile does not select a new bridge or mandate a native rewrite.

## One Owner for Each Rule and State

- Implement an equipment rule with one domain owner; presentation and Ellie use its public contracts.
- Distinguish actual physical state from observations, retained sensor readings, and knowledge.
- Keep configured capacity, stored resources, connected availability, and actual consumption distinct where the equipment specification requires it.
- Persist and restore coherent authoritative state. Save formats, view models, and caches do not define a second simulation.
- Keep fictional service-network topology distinct from software dependency direction.

These are implementation boundaries. Numerical ratings, equations, fault behavior, access rules, and scenario outcomes must come from their actual source owners rather than this handbook.

## Prototype Development

Build the smallest authorized end-to-end capability across real boundaries. In-memory adapters, authored responses, simplified content, and manual composition can support discovery when the task identifies the simplification and preserves the required behavior.

Keep provisional code easy to extract. Promote stable rules into cohesive domain modules, and keep provider, engine, persistence, and transport details outside them. Scope performance and fidelity work to demonstrated needs.

The opening prototype has its own construction boundary. This handbook's creation does not authorize any milestone, live inference integration, art production, or broader campaign implementation.

## Design Source Availability

The full authoring workspace has these established subject owners:

| Workspace family | Detailed owner |
| --- | --- |
| `systems_architecture/` | Ship equipment capabilities, constraints, and physical operating rules. |
| `game_design/` | Player interaction, missions, progression, consequences, and acceptance outcomes. |
| `software_architecture/` | Runtime structure, interfaces, representation, persistence, Ellie integration, and technical fixtures. |
| `lore/` | Fictional context and history. |
| `governance/` | Documentation responsibility, status, adoption, and decision provenance. |
| `assets/` | Asset authority and production protocols within their stated scope. |

This initial handbook does not publish those collections. The paths are an ownership inventory, not links to content guaranteed present in every clone.

Before implementation or substantive requirements review, the work packet must identify the required owning documents at an accessible repository ref or an explicitly supplied workspace location. Record the ref or source state used. Request the missing inputs if those sources cannot be accessed; continue independent authorized work where possible.

Do not substitute private memory, this inventory, or an invented approximation for the actual requirement. Publishing further source collections is a separate scoped action, especially for assets and unpublished campaign material.

## Local Code Contracts

Use [source organization](source_organization.md) to locate the planned implementation homes for these responsibilities. This profile continues to own runtime authority and design-source availability.

Add or reconcile `__ai__.md` files as durable implementation concerns emerge. Follow the [local contract standard](../Canon/Architecture/Craig-Architecture-__ai__-Template.md). Use [Python guidance](../Canon/Architecture/Craig-Architecture-Python.md) where Python is involved.

The initial documentation check is defined by the [verification contract](verification_contract.md). Application checks become executable requirements only when the implementation task configures them and records their commands and scope.
