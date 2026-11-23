"""Adapt local M0 messages to the existing authoritative command/event service."""

from math import isfinite
from secrets import compare_digest
from typing import cast

from koios_sim.domain.traversal.operation import Waypoint
from koios_sim.domain.traversal.world import Point
from koios_sim.interfaces.live_snapshot import encode_feedback, encode_snapshot
from koios_sim.interfaces.operations import execute
from koios_sim.services.traversal.contracts import (
    ManualCycleResult,
    PhysicalEvent,
)
from koios_sim.services.traversal.manual_control import RoutePose
from koios_sim.services.traversal.session import Session

MAX_ADVANCE_MS = 250


class MessageError(ValueError):
    """Reject malformed input before game state changes."""


class Bridge:
    """One authenticated, ordered M0 delivery session over an injected application.

    Owns a connection-local nonce check, sequence and feedback cursor, not ship
    time, world state or work. A new connection gets a new bridge; rejected
    protocol messages do not advance its cursor or acknowledge a request.
    """
    def __init__(self, session: Session, nonce: str) -> None:
        self._session = session
        self._nonce = nonce
        self._sequence = 0
        self._authenticated = False
        self._feedback_cursor = 0

    def handle(self, message: dict[str, object]) -> dict[str, object]:
        """Validate and dispatch one v1 message, then return newly delivered feedback.

        Malformed protocol or rejected physical-completion reports raise MessageError
        rather than acknowledging the sequence. A valid manual/control request can
        return an unconfirmed note with an acknowledgement, as distinct from a
        protocol error. Application feedback remains owned by Session.
        """
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
            "state": encode_snapshot(self._session.snapshot()),
            "feedback": [encode_feedback(entry) for entry in feedback[before:]],
        }

    def _manual_cycle(self, message: dict[str, object]) -> bool:
        """Decode transport fields without preempting application admission order."""
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


def _event(payload: object) -> PhysicalEvent:
    """Decode a waypoint report; identity, geometry and timing are checked by Session."""
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
    """Decode the existing route sample, with the independent wire interval cap."""
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
