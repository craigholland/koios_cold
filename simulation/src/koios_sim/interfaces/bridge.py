"""Adapt local M0 messages to the existing authoritative command/event service."""

from dataclasses import asdict
from math import isfinite
from secrets import compare_digest
from typing import cast

from koios_sim.domain.traversal.observation import observe
from koios_sim.domain.traversal.operation import Waypoint
from koios_sim.domain.traversal.world import DoorPosition, Point
from koios_sim.interfaces.operations import USAGE, execute
from koios_sim.services.traversal.contracts import Feedback, PhysicalEvent
from koios_sim.services.traversal.session import Session

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
            self._tick(message)
        elif kind == "pause":
            self._session.set_paused(_bool(message, "paused"))
        elif kind == "manual_begin":
            if not self._session.begin_manual(_text(message, "drone_id")):
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
            "state": _snapshot(self._session),
            "feedback": [_feedback(entry) for entry in feedback[before:]],
        }

    def _manual_cycle(self, message: dict[str, object]) -> bool:
        session = self._session
        point = Point(_number(message, "x_m"), _number(message, "y_m"))
        heading = _number(message, "heading")
        release = _bool(message, "release")
        lease = _text(message, "lease_id")
        drone = _text(message, "drone_id")
        if (session.manual is None or session.manual.id != lease
                or session.manual.drone_id != drone or session.paused
                or _int(message, "stamp_ms", 0) != session.stamp_ms):
            return False
        self._tick(message)
        return session.report_manual(lease, drone, session.stamp_ms, point, heading,
                                     release=release)

    def _tick(self, message: dict[str, object]) -> None:
        elapsed = _int(message, "elapsed_ms", 0)
        if elapsed > MAX_ADVANCE_MS:
            raise MessageError("tick exceeds the dev interval limit")
        self._session.advance(elapsed)


def _feedback(value: Feedback) -> dict[str, object]:
    return asdict(value)


def _snapshot(session: Session) -> dict[str, object]:
    order = session.order
    door = session.world.door
    fraction = 1.0 if door.position is DoorPosition.OPEN else 0.0
    if session.opening is not None and not door.jammed:
        fraction = 1.0 - session.opening.remaining_ms / session.timing.opening_ms
    active: dict[str, object] | None = None
    if order is not None:
        active = {
            "command_id": order.command_id,
            "step": order.index + 1,
            "phase": order.phase,
            "verb": order.current.verb,
            "room_id": order.current.target_id,
            "checkpoint_seen": order.crossed,
            "waypoint_ready": order.segment_ms >= session.timing.waypoint_ms,
        }
    return {
        "world": asdict(session.status()),
        "stamp_ms": session.stamp_ms,
        "paused": session.paused,
        "opening_fraction": fraction,
        "active": active,
        "manual": None if session.manual is None else session.manual.id,
        **_presentation(session, fraction),
    }


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


def _presentation(session: Session, fraction: float) -> dict[str, object]:
    world, sensing = session.world, session.sensing
    facts = world.door.services
    telemetry = (facts.controller_powered and facts.controller_healthy
                 and facts.controller_data_connected)
    door_report = {"position": world.door.position, "stamp_ms": session.stamp_ms,
                   "source": "controller"} if telemetry else None
    if sensing is None:
        return {}
    has_feed = world.drone.local_dcl_signal and world.drone.workstation_route_available
    evidence = observe(world, sensing, fraction) if has_feed else None
    if evidence is not None:
        session.discovered_markers.update(marker.id for marker in evidence.visible_markers)
    return {
        "door_report": door_report,
        "sensor": asdict(evidence) if evidence is not None else None,
        "discovered_markers": sorted(session.discovered_markers),
        "steering": {"speed_m_s": sensing.speed_m_s, "turn_deg_s": sensing.turn_deg_s},
        "completion": {
            "verbs": sorted(USAGE),
            "deck": session.context,
            "slot": str(world.drone.slot),
            "rooms": [room.id for room in world.rooms],
            "doors": [world.door.id],
        },
    }
