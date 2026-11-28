"""Serialize detached application snapshots and feedback to the M0 v1 wire shape."""

from dataclasses import asdict

from koios_sim.interfaces.operations import USAGE
from koios_sim.services.traversal.contracts import Feedback
from koios_sim.services.traversal.snapshots import SessionSnapshot


def encode_feedback(value: Feedback) -> dict[str, object]:
    return asdict(value)


def encode_snapshot(value: SessionSnapshot) -> dict[str, object]:
    """Map an immutable read model to v1 keys without access to the live Session.

    Headless sessions omit the existing presentation key group rather than
    sending placeholders. Wire-specific grammar, field names, and casing stay here.
    """
    active, door = value.active, value.door_activity
    result = {
        "world": asdict(value.world),
        "stamp_ms": value.stamp_ms,
        "paused": value.paused,
        "opening_fraction": value.opening_fraction,
        "door_activity": {
            "command_id": door.command_id, "phase": "opening" if door.opening else "queued",
            "door_id": door.door_id, "origin": door.origin,
        } if door is not None else None,
        "door_energy_mj": {"controller": value.controller_energy_mj, "mechanism": value.mechanism_energy_mj},
        "active": {
            "command_id": active.command_id, "step": active.step, "phase": active.phase,
            "verb": active.current.verb, "room_id": active.current.target_id,
            "checkpoint_seen": active.crossed, "waypoint_ready": active.waypoint_ready,
        } if active is not None else None,
        "manual": value.manual_lease,
    }
    if value.steering is not None:
        report, sensor = value.door_report, value.observation
        result.update({
            "door_report": {**asdict(report), "source": "controller"} if report is not None else None,
            "sensor": asdict(sensor) if sensor is not None else None,
            "discovered_markers": list(value.discovered_markers),
            "known_markers": [asdict(marker) for marker in value.known_markers],
            "steering": asdict(value.steering),
            "completion": {
                "verbs": sorted(USAGE), "deck": value.context, "slot": str(value.world.drone.slot),
                "rooms": [room.id for room in value.world.rooms], "doors": [value.world.door.id],
            },
        })
    return result
