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

Own the headless Python M0 simulation, its developer query, and its test fixture.
Godot, player-facing commands, persistence, and campaign content are not yet implemented.

## Dependencies and Architectural Rules

Domain imports the standard library only and does not perform filesystem or runtime
setup. Services consume domain types. Interfaces format application results.
Composition binds the package resource and developer entry point. Do not read
developer fixture files from inward layers or create an independent frontend world.

## Public API and File Index

- `domain/traversal/world.py`: canonical in-memory world and invariant checks.
- `services/traversal/status.py`: read-only `get_status(world)` application query.
- `interfaces/cli.py`: developer JSON output only.
- `composition/fixture.py` and `composition/fixtures/m0.json`: decode and instantiate the
  provisional definition; geometry and initial values have one owner.
- `composition/main.py`: installed developer entry point.
- `tests/`: fixture, query, dependency direction, and CLI checks.

## Verification Contract

Use [the installation and check commands](README.md#windows-setup-and-verification).
Report the actual Python version, checked head, and skipped checks. This local contract
does not adopt production hardware values or certify Godot or hosted CI.
