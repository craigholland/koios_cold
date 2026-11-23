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
views, scoped direct steering, and basic local audio. M0 completion remains a
review and owner decision; this does not authorize M1/M2.

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
the launcher. Relaunch to reset the entire fixture (not a player save or recovery feature).

Enter echoes each captured line in the transcript with a `>` prompt. The local
buffer holds up to four waiting lines in entry order, in addition to a command
already awaiting acknowledgement. They send automatically as the bridge becomes
available. Enter keeps the field ready for the next line. The activity strip labels
waiting console lines separately; local capture is not Python acceptance.
If the buffer is full, the new line remains in the input field for deliberate retry.

On connection loss, lines still held locally are reported as not sent. A line
handed to the bridge without a verified response is reported as not confirmed.
The scene stays responsive, freezes at its last confirmed state, and disables
submission. Start a fresh fixture to continue; no line is replayed automatically.

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

## Local audio and confirmed feedback

In Drone view, the simulated microphone has a quiet ambience bed, a motor
cue for translation or in-place turn, strain for actual resisted movement,
and a one-shot impact for initial physical contact. Schematic, a paused
clock, lost desktop focus, missing feed evidence, and lost backend mute this
channel. Returning to Drone plays current activity only; it does not replay
missed impacts. This does not grant microphone permission or add damage.
See [original placeholder audio provenance](assets/audio/README.md).

The work strip and console report confirmed command/step and door-operation
IDs. Queued/waiting work is not complete; an accepted separate door request
still takes actual mechanism time. The visual obstruction label does not
require hearing the strain or collision cue. Any unacknowledged request
remains uncertain after disconnect.

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
reports (including actual heading) using the last acknowledged Python timestamp and active order
identity/step. The authoritative clock, commands and lasting state remain
in Python. Manual pose reports carry the current direct-control ID and ship stamp.
Takeover during a move reconciles the actual pose against the prior order before
cancelling it. The shared fixture radius and actual leaf aperture determine crossing
even during a sufficiently wide partial opening.
During autonomous travel, the existing clock tick can carry one validated route
pose. The same Python state drives current observation and the sensor cone; the
sample does not count as arrival or add per-frame bridge calls. The Godot mover
turns in place toward each next autonomous waypoint at the provisional turn
rate, then travels forward at the fixture speed. The arrival report confirms
point and heading together for the same forward sensing; manual reverse still
moves backward without turning.
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
& $python -c $launcher $console --headless --path frontend --script res://tests/handoff_checks.gd -- --sensing
& $python -c $launcher $console --headless --path frontend --script res://tests/autonomous_heading_checks.gd
& $python -c $launcher $console --headless --path frontend --script res://tests/conformance_checks.gd
& $python -c $launcher $console --headless --path frontend --script res://tests/conformance_checks.gd -- --interruption
& $python -c $launcher $console --headless --path frontend --script res://tests/command_console_checks.gd
& $python -c $launcher $console --headless --path frontend --script res://tests/command_console_checks.gd -- --loss
& $python -c $launcher $godot --log-file frontend/.godot/m0-mix-log.txt --path frontend --script res://tests/conformance_checks.gd -- --measure-audio
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

The integrated headless run uses Dummy audio and verifies cue and application
state only. The rendered mix run requires a non-Dummy Windows audio driver and
checks downstream PCM (positive motor, strain, and collision; Schematic muted
during motion; resumed current motor without stale collision; separate pause
window focus, and connection-loss silence after settling). It does not record a microphone
or certify loudspeaker output or subjective sound quality.

## M0 requirement crosswalk and limits

| Existing requirement | Evidence or remaining boundary |
| --- | --- |
| PROTOTYPE-01 | Live bridge uses Python-owned commands, clock and state; round-trip and interruption checks inspect confirmed outcomes. |
| PROTOTYPE-02 | One m0 fixture: Drone 01 in slot 1, R1/D1/R2, working local DCL signal and workstation route; both views share the pose and actual door, with different evidence channels. |
| PROTOTYPE-03 | Live control checks cover forward/reverse, turn-in-place, release, text focus, native window focus, pause and real takeover. |
| PROTOTYPE-04 | Integrated cases cover wait, read-only status/queue inspection, separate opening/resume/arrival, stop without revival, and move/navigate alias parity; the command IDs trace actual outcomes. |
| PROTOTYPE-05 | Original ambience/motor/strain/impact cues follow actual local activity in Drone only. Deployment audio and Fast Forward behavior have no trigger in this M0 fixture and are not implemented or claimed. |
| PROTOTYPE-23 | The package labels provisional geometry, sensing/time/energy and audio separately from adopted game rules. Live Ellie, campaign/solar deployment, ship-wide systems, production saves, and other applications remain out of scope. |
| PROTOTYPE-25 | No formal tester recruitment, observation protocol, subjective score, or playtest claim. These are executable technical checks only. |

Reference captions: [room/door sketch](../assets/sketch/example_deck_traversal.png)
illustrates connectivity; only R1-D1-R2 is included. The
[Duskers schematic](../assets/sketch/Schematic1.PNG) informs readable labels,
and the [Duskers drone view](../assets/sketch/Drone1.PNG) informs local cues;
neither supplies Koios art, commands, or rules.
