"""Adapt local M0 messages to the existing authoritative command/event service."""

from dataclasses import asdict
from math import isfinite
from secrets import compare_digest
from typing import cast

from koios_sim.domain.traversal.operation import Waypoint
from koios_sim.domain.traversal.world import Point
from koios_sim.interfaces.operations import USAGE, execute
from koios_sim.services.traversal.contracts import (
    Feedback,
    ManualCycleResult,
    PhysicalEvent,
)
from koios_sim.services.traversal.manual_control import RoutePose
from koios_sim.services.traversal.session import Session
from koios_sim.services.traversal.snapshots import SessionSnapshot

MAX_ADVANCE_MS = 250


class MessageError(ValueError):
    """Reject malformed input before game state changes."""


class Bridge:
    def __init__(self, session: Session, nonce: str) -> None:
        self._session = session
        self._nonce = nonce
        self._sequence = 0
        self._authenticated = False
        self._feedback_cursor = 0

    def handle(self, message: dict[str, object]) -> dict[str, object]:
        seq = _int(message, "seq", 1)
        if seq != self._sequence + 1:
            raise MessageError("request sequence mismatch; not executed")
        kind = _text(message, "kind")
        note = None
        if not self._authenticated:
            if (kind != "hello" or _int(message, "version", 1) != 1
                    or not compare_digest(_text(message, "nonce").encode(), self._nonce.encode())):
                raise MessageError("invalid local handshake")
            self._authenticated = True
        elif kind == "command":
            source = _text(message, "text")
            if not 0 < len(source) <= 512:
                raise MessageError("command length out of range")
            execute(self._session, source, origin="godot")
        elif kind == "tick":
            raw = message.get("route_pose")
            pose = None if raw is None else _route_pose(raw)
            elapsed = _int(message, "elapsed_ms", 0)
            if pose is not None and pose.elapsed_ms != elapsed:
                raise MessageError("pose interval must match tick interval")
            if elapsed > MAX_ADVANCE_MS:
                raise MessageError("tick exceeds the dev interval limit")
            self._session.apply_tick(elapsed, pose)
        elif kind == "pause":
            self._session.set_paused(_bool(message, "paused"))
        elif kind == "manual_begin":
            raw = message.get("handoff")
            handoff = None if raw is None else _route_pose(raw)
            if not self._session.begin_manual(_text(message, "drone_id"), handoff):
                note = "Direct control unavailable."
        elif kind == "manual_cycle":
            if not self._manual_cycle(message):
                note = "Direct motion was not confirmed."
        elif kind == "physical":
            if not self._session.report_physical(_event(message.get("event"))):
                raise MessageError("physical result rejected; no completion acknowledged")
        else:
            raise MessageError("unsupported message type")
        self._sequence = seq
        feedback = self._session.feedback()
        before = self._feedback_cursor
        self._feedback_cursor = len(feedback)
        return {
            "seq": seq,
            "kind": "snapshot",
            "note": note,
            "state": _snapshot(self._session.snapshot()),
            "feedback": [_feedback(entry) for entry in feedback[before:]],
        }

    def _manual_cycle(self, message: dict[str, object]) -> bool:
        point = Point(_number(message, "x_m"), _number(message, "y_m"))
        heading = _number(message, "heading")
        release = _bool(message, "release")
        lease = _text(message, "lease_id")
        drone = _text(message, "drone_id")
        # Timing field errors are reported only when the application admits that part of a cycle.
        stamp = _optional_int(message, "stamp_ms")
        elapsed = _optional_int(message, "elapsed_ms")
        interval = elapsed if elapsed is not None and elapsed <= MAX_ADVANCE_MS else None
        result = self._session.manual_cycle(lease, drone, stamp, interval, point, heading, release=release)
        if result is ManualCycleResult.INVALID_STAMP:
            raise MessageError("stamp_ms must be an integer >= 0")
        if result is ManualCycleResult.INVALID_INTERVAL:
            if elapsed is None:
                raise MessageError("elapsed_ms must be an integer >= 0")
            raise MessageError("tick exceeds the dev interval limit")
        return result is ManualCycleResult.CONFIRMED


def _feedback(value: Feedback) -> dict[str, object]:
    return asdict(value)


def _snapshot(value: SessionSnapshot) -> dict[str, object]:
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
            "steering": asdict(value.steering),
            "completion": {
                "verbs": sorted(USAGE), "deck": value.context, "slot": str(value.world.drone.slot),
                "rooms": [room.id for room in value.world.rooms], "doors": [value.world.door.id],
            },
        })
    return result


def _event(payload: object) -> PhysicalEvent:
    if not isinstance(payload, dict):
        raise MessageError("expected event object")
    source = cast(dict[str, object], payload)
    try:
        waypoint = Waypoint(_text(source, "waypoint"))
    except ValueError as exc:
        raise MessageError("unknown waypoint") from exc
    return PhysicalEvent(
        _text(source, "command_id"),
        _int(source, "step", 1),
        _text(source, "drone_id"),
        _int(source, "stamp_ms", 0),
        waypoint,
        _text(source, "target_id"),
        Point(_number(source, "x_m"), _number(source, "y_m")),
        _number(source, "heading"),
    )


def _text(source: dict[str, object], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str):
        raise MessageError(f"{key} must be text")
    return value


def _int(source: dict[str, object], key: str, minimum: int) -> int:
    value = source.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MessageError(f"{key} must be an integer >= {minimum}")
    return value


def _number(source: dict[str, object], key: str) -> float:
    value = source.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise MessageError(f"{key} must be finite")
    try:
        if isfinite(value):
            return float(value)
    except OverflowError:
        pass
    raise MessageError(f"{key} must be finite")


def _bool(source: dict[str, object], key: str) -> bool:
    value = source.get(key)
    if type(value) is not bool:
        raise MessageError(f"{key} must be boolean")
    return value


def _optional_int(source: dict[str, object], key: str) -> int | None:
    value = source.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _route_pose(payload: object) -> RoutePose:
    if not isinstance(payload, dict):
        raise MessageError("handoff must be an object")
    handoff = cast(dict[str, object], payload)
    elapsed = _int(handoff, "elapsed_ms", 0)
    if elapsed > MAX_ADVANCE_MS:
        raise MessageError("handoff exceeds the dev interval limit")
    return RoutePose(
        _text(handoff, "command_id"), _int(handoff, "step", 1),
        _int(handoff, "stamp_ms", 0), elapsed,
        Point(_number(handoff, "x_m"), _number(handoff, "y_m")),
        _number(handoff, "heading"),
    )
