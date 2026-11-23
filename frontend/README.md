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
or the separate Drone and Schematic views. Direct steering, full view
interaction, sound and integrated M0 sign-off are later work.

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
in Python. Motion on-screen before the next confirmation is physical
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
```

The smoke runs the actual scene, command service and movement, then exits
after Python confirms R2; it is not a full interaction or art review.
The bridge and collision scripts test framing, pending-ack disconnection,
and passage under closed, too-narrow and open leaves. Check engine stderr
as well as result markers. The [verification contract](../docs/Authoritative/Identity/verification_contract.md)
owns the inherited Python, handbook and whitespace checks.
