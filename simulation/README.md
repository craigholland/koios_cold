# Koios Cold simulation

This first M0 slice installs a headless Python package. It displays the real read-only
world query for one provisional drone, two flat rooms and one ordinary sliding door.
It does not implement player commands, movement, Godot, persistence or campaign content.

## Windows setup and verification

From the repository root with CPython 3.14 installed (verified on Windows x64
with CPython 3.14.2):

```powershell
py -3.14 -m venv simulation/.venv
$python = ".\simulation\.venv\Scripts\python.exe"
& $python -m pip install ".\simulation[dev]"
& $python -m koios_sim.composition.main
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
