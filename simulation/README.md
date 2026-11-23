---
title: "Koios Cold Simulation"
created_date: 2026-11-23
update_date: 2026-11-23
status: APPROVED
tags: [simulation, m0, python, development-setup, headless-checks]
---

# Koios Cold simulation

This headless M0 package displays the real read-only
world query for one provisional drone, two flat rooms and one ordinary sliding door.
It also exercises the deterministic M0 Operations subset. It does not run a Godot
physics simulation, persistence or campaign content.

## Windows setup and verification

From the repository root with CPython 3.14 installed (verified on Windows x64
with CPython 3.14.2):

```powershell
py -3.14 -m venv simulation/.venv
$python = ".\simulation\.venv\Scripts\python.exe"
& $python -m pip install ".\simulation[dev]"
& $python -m koios_sim.composition.main
& $python -m koios_sim.composition.replay
& $python -m pytest simulation/tests
& $python -m ruff check simulation/src simulation/tests
& $python -m mypy --config-file simulation/pyproject.toml simulation/src
```

The standard installation also supplies `simulation/.venv/Scripts/koios-m0.exe`.
No working-directory requirement or `PYTHONPATH` override is needed for the installed
query. The application has no third-party runtime dependencies.

## Fixture and ownership

The packaged [M0 manifest](src/koios_sim/composition/fixtures/m0.json) is the single
editable starting definition for later runtimes. X/Y coordinates and the clear door
opening are in metres; heading is clockwise in degrees from +X with +Y down.
Charge and capacity are in watt-hours, and condition is a percent. Values and
geometry are provisional development inputs, not campaign or hardware ratings.
The two DCL fields describe separate local signal and Workstation route facts;
controller health/power, Data, mechanism power, access and pressure are separate.

Domain entities validate world relationships. Composition reads and decodes the
manifest once per world; `services.traversal.status.get_status(world)` projects
that world, not a second decoded copy. The developer CLI formats that query
without adding a player-facing grammar.

Game rules are governed by the task-supplied opening prototype, Workstation,
drone, controls and door owners; runtime ownership follows the software architecture
sources named in issue #15. Unpublished sources are not included here.

## Headless Operations replay

Run the replay command above for the actual sequence: `move 1 R2; open D1`
waits at D1; `status 1` and `queue show 1` inspect without replacing work;
a separate `open D1` starts the door. Advancing semantic time completes opening
and automatically resumes the retained route. The developer replay then injects
a doorway checkpoint and an arrival, in that order. An accepted request alone
never establishes arrival or opens a door.

Python owns a single world and accepts physical reports only for the current
instruction, step, permanent drone identity and current semantic timestamp.
Cross-room arrivals need a reported point through the actual open D1 aperture
followed by a point inside the target room. The doorway report is a checkpoint,
not a room/position update; the arrival reconciles the last confirmed room and
location. Fixture waypoint duration is a small accounting guard, not simulated
locomotion or a final travel-speed rating. A subsequent Godot slice must report
results from real movement. Pausing freezes progress and drains; status/queue
reads never change accepted work.

The manifest's time values are in integer milliseconds and drone power in
integer watts. Semantic energy debits use integer millijoules (W × ms); initial
and projected charge in Wh is converted with nearest-mJ rounding (half up) and
never raised by a debit. Travel fails when charge can no longer fund a full
millisecond of travel. Larger steps split at that instant; remaining elapsed
time uses the idle drain. Status reports six decimal places for Wh.
Controller and mechanism support draw from the separate external supply:
20 W while controller power is supplied, and 500 W during actual mechanism
activity, including a powered jam attempt. Loss of a required service aborts
an opening without crediting outage time; restored service allows a fresh
request. Door duration and drone tuning are
provisional fixture inputs, not adopted ratings or campaign reserve values.
