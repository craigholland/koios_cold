---
title: "Live M0 Frontend Local Contract"
created_date: 2026-11-23
update_date: 2026-11-23
status: APPROVED
tags: [godot, m0, local-contract, presentation, bridge]
---

# Live M0 frontend local contract

## Last Verified (CI)

No hosted frontend CI is configured. See the PR handoff for local results.

## Scope and dependencies

Godot owns presentation, physical movement and collision. Python is the sole
source of topology and lasting state. The frontend can project the application
snapshot and report bounded physical outcomes; it cannot infer completion
from an unacknowledged submission or define simulation power or timing rules.
Current scope is one shared fixed overhead scene with Schematic and Drone
projections, focused direct controls and bounded local microphone cues.

## File index and public boundary

- `app/sandbox.tscn` and `sandbox.gd`: compose the scene, status, command UI,
  semantic requests and the bounded traversal smoke.
- `features/traversal/room_view.gd`: both projections, sliding-door colliders
  and real local movement.
- `components/audio/drone_monitor.gd`: gates original cue playback from actual motion
  and view/connection state; it never owns damage or resource effects.
- `input/m0_controls.gd`: scoped bindings and fresh-press focus gate.
- `input/command_draft.gd`: history and draft; inserts only Python-known tokens.
- `input/command_delivery.gd`: bounded, session-local FIFO waiting for bridge
  transmission; never owns accepted work, and reports unsent versus unconfirmed
  lines on loss. The scene echoes captured lines and keeps backend feedback distinct.
- `bridge/json_frames.gd` and `local_client.gd`: bounded loopback transport,
  one in-flight sequence, errors and uncertain outcomes without replay.
- `tests/`: executable bridge, movement, focus and integrated conformance checks.

## Verification

Follow the [frontend setup and checks](README.md#verification). Use the
[simulation contract](../simulation/__ai__.md) for Python ownership and the
launcher. Do not report a headless pass as rendered or hosted CI evidence.
