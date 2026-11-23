---
title: "Koios Cold Live M0 Sandbox"
created_date: 2026-11-23
update_date: 2026-11-23
status: APPROVED
tags: [m0, godot, python, local-bridge, developer-verification]
---

# Koios Cold live M0 sandbox

This standalone development scene runs the existing one-drone, two-room,
one-door fixture through Python and Godot. It is not the opening campaign
or a claim that M0 is finished. It provides the Schematic and deck-aligned Drone
views plus scoped direct steering. Sound and final integrated sign-off are later.

## Windows setup and launch

Verified on Windows x64 with CPython **3.14.2** and Godot
**4.6.3.stable.official.7d41c59c4** (standard, not .NET). Use the official
Godot archive. Extract it outside the repository; keep the main and console
executables together. No PATH, project setting or firewall change is needed.

From the repository root, follow the [simulation install](../simulation/README.md#windows-setup-and-verification)
or run these steps:

```powershell
py -3.14 -m venv simulation/.venv
$python = ".\simulation\.venv\Scripts\python.exe"
& $python -m pip install ".\simulation[dev]"
$godot = (Read-Host "Path to Godot's main Windows .exe")
$console = $godot -replace '\.exe$', '_console.exe'
& $console --headless --path frontend --editor --import
& $python -m koios_sim.composition.live --godot $godot
```

Start from the Python launcher, not from the scene alone: the latter has no
semantic session. Type `move 1 R2`, wait for D1, use `status 1` or
`queue show 1` if desired, then type `open D1`. Godot moves the drone after
opening and Python confirms actual arrival. Close the scene window to end
the launcher. Relaunch starts a fresh dev fixture (not a player save feature).

Pending requests are never replayed. If the command is locally busy, the
input is retained for a deliberate retry. If the backend goes away before
acknowledgement, the scene remains responsive, freezes at its last confirmed
state and disables submission. Start a fresh fixture to continue.

## Views, controls and focus

- Press **0** for Schematic or **1** for the assigned Drone view outside Command
  Input. This does not pause or retarget accepted work. Both views share pose,
  heading, and door geometry; Schematic separates controller evidence from the
  blueprint and Drone view shows only current local light/line-of-sight.
- In Drone view, Left/Right turn in place and Up/Down drive forward/reverse
  relative to the drone's heading. Releasing controls or leaving focus stops
  steering immediately. A new nonrepeat key press is required after return.
  Accepted manual takeover replaces the existing autonomous route.
- With Command Input focused, ordinary typing/digits and arrows are text/history
  controls; Enter submits, Tab completes allowed tokens and Escape exits text
  focus without issuing a stop. Drafts and history survive view changes.
- **F3** toggles the semantic clock even from Command Input. Paused input
  cannot move the drone or take over its route.
- Optional bindings are stored in Godot's local `user://m0-bindings.json`.
  Example: `{"forward":"W","reverse":"S","left":"A","right":"D"}`.
  Supported action keys are `forward`, `reverse`, `left`, `right`, `schematic`,
  `drone`, and `pause`. Use one physical key per action; duplicate bindings,
  unknown keys, and Enter/Tab/Escape are rejected without changing defaults.
Global pause can use F1–F12 only so remapping cannot steal ordinary typing.

## Runtime seam

The launcher starts one Godot process and serves one ephemeral IPv4 loopback
connection. A launch-local nonce distinguishes the intended local client.
The versioned dev framing is bounded UTF-8 newline-delimited JSON with
monotonic request sequence numbers and one request in flight. No remote
hosting, persistence, automatic reconnect or shipping transport is implied.

The snapshot projects the installed [single Python fixture](../simulation/src/koios_sim/composition/fixtures/m0.json)
and its live state. Godot owns frame-rate movement and colliders, including
the two sliding leaves; no per-frame round trip is needed. Arrival comes from
actual movement, not from rendering the requested destination. The client
sends bounded elapsed-millisecond requests and meaningful doorway/arrival
reports using the last acknowledged Python timestamp and active order
identity/step. The authoritative clock, commands and lasting state remain
in Python. Manual pose reports carry the current direct-control ID and ship stamp.
Takeover during a move reconciles the actual pose against the prior order before
cancelling it. The shared fixture radius and actual leaf aperture determine crossing
even during a sufficiently wide partial opening.
The provisional fixture defines speed, turn, light reach and sight angle, not new
hardware ratings. One non-interactive marker tests limited discovery; its ID and
location are not sent until observation permits them. Motion before confirmation is
presentation, not a second durable room state.

## Verification

After the install/import above, from the repository root:

```powershell
& $python -m pytest simulation/tests
& $console --headless --path frontend --script res://app/sandbox.gd --check-only
& $console --headless --path frontend --script res://tests/bridge_checks.gd
& $console --headless --path frontend --script res://tests/movement_checks.gd
& $python -m koios_sim.composition.live --godot $console --headless --smoke
& $python -m koios_sim.composition.live --godot $godot --smoke
& $python -m koios_sim.composition.live --godot $console --headless --control-check
& $python -m koios_sim.composition.live --godot $godot --control-check --native-focus
$launcher = 'from koios_sim.composition.live import launch; import sys; sys.exit(launch(sys.argv[1:]))'
& $python -c $launcher $console --headless --path frontend --script res://tests/handoff_checks.gd
& $python -c $launcher $console --headless --path frontend --script res://tests/handoff_checks.gd -- --partial
```

The smoke runs the actual scene, command service and movement, then exits
after Python confirms R2; it is not a full interaction or art review.
The bridge and collision scripts test framing, pending-ack disconnection,
and passage under closed, too-narrow and open leaves. Check engine stderr
as well as result markers. The control check injects keys against the actual scene
and backend. Its headless mode simulates focus notices; the native mode opens a
dedicated second window to exercise actual Windows focus loss and return. The handoff script runs the real mover against Python, taking over mid-route
or crossing a physically passable partial opening. The [verification contract](../docs/Authoritative/Identity/verification_contract.md)
owns the inherited Python, handbook and whitespace checks.
