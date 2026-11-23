---
title: "Koios Simulation Local Contract"
created_date: 2026-11-23
update_date: 2026-11-23
status: APPROVED
tags: [simulation, m0, local-contract, headless-checks]
---

# Koios Simulation Local Contract

## Last Verified (CI)

No hosted application CI is configured. Use the PR handoff for executed local results.

## Scope and Purpose

Own the headless Python M0 simulation, its developer query/replay, and its test fixture.
The deterministic M0 Operations subset is available headlessly and through the
[live Godot sandbox](../frontend/README.md). Godot owns continuous physics;
persistence and campaign content remain outside this implementation.

## Dependencies and Architectural Rules

Domain imports the standard library only and does not perform filesystem or runtime
setup. Services consume domain types. Interfaces format application results.
Composition binds the package resource and developer entry point. Do not read
developer fixture files from inward layers or create an independent frontend world.

## Public API and File Index

- `domain/traversal/world.py`: canonical in-memory world and invariant checks.
- `services/traversal/status.py`: read-only `get_status(world)` application query.
- `domain/traversal/operation.py`: route, door, fixture timing and resource predicates.
- `services/traversal/session.py` and `orders.py`: one live semantic state, clock and work.
- `services/traversal/commands.py` and `contracts.py`: identity binding, structured requests,
  feedback and physical reports, including heading in live waypoint confirmation.
- `domain/traversal/observation.py` and `manual.py`: bounded sensing/occlusion,
  and manual pose geometry. `services/traversal/manual_control.py` reconciles
  only the active direct-control lease; the session owns discovery and authority.
- `interfaces/cli.py`: developer JSON status output; `interfaces/operations.py`: grammar.
- `composition/replay.py`: deterministic developer command and physical-event replay.
- `composition/live.py`: starts and owns the isolated frontend child and loopback socket.
- `interfaces/bridge.py` and `interfaces/frames.py`: adapt ordered requests to the same
  Operations service and serialize confirmed snapshots, timed door work, independent
  resource counters and feedback. The frontend may display facts, not derive completion.
- `composition/fixture.py` and `composition/fixtures/m0.json`: decode and instantiate the
  provisional definition; geometry and initial values have one owner.
- `composition/main.py`: installed developer entry point.
- `tests/`: fixture, query, dependency direction, and CLI checks.

## Verification Contract

Use [the installation and check commands](README.md#windows-setup-and-verification).
Report the actual Python version, checked head, and skipped checks. This local contract
does not adopt production hardware values or certify Godot or hosted CI.
