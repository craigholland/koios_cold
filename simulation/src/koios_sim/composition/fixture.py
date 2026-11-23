"""Decode the packaged provisional geometry and instantiate an independent world."""

import json
from collections.abc import Callable
from importlib.resources import files
from math import isfinite
from typing import TypeVar, cast

from koios_sim.domain.traversal.observation import Marker, Sensing
from koios_sim.domain.traversal.operation import Timing
from koios_sim.domain.traversal.world import (
    Door,
    DoorPosition,
    DoorServices,
    Drone,
    Point,
    Room,
    World,
)

T = TypeVar("T")


class FixtureError(ValueError):
    """Invalid fixture input; the cause names the relevant field."""


def load_m0() -> World:
    return load_scenario()[0]


def load_scenario() -> tuple[World, Timing]:
    world, timing, _ = load_live_scenario()
    return world, timing


def load_live_scenario() -> tuple[World, Timing, Sensing]:
    resource = files(__package__).joinpath("fixtures", "m0.json")
    return _decode_live(resource.read_text(encoding="utf-8"))


def decode_fixture(text: str) -> World:
    return decode_scenario(text)[0]


def decode_scenario(text: str) -> tuple[World, Timing]:
    world, timing, _ = _decode_live(text)
    return world, timing


def _decode_live(text: str) -> tuple[World, Timing, Sensing]:
    try:
        root = _record(json.loads(text, object_pairs_hook=_unique_object), "fixture", (
            "classification", "deck_id", "rooms", "door", "drone", "timing", "sensing",
        ))
        if root["classification"] != "provisional-development-fixture":
            raise FixtureError("fixture classification must be provisional-development-fixture")
        a, b = _pair(root["rooms"], "rooms")
        world = World(_string(root["deck_id"], "deck_id"), (_room(a), _room(b)),
                      _door(root["door"]), _drone(root["drone"]))
        timings = _Fields(root["timing"], "timing", (
            "opening_ms", "waypoint_ms", "idle_w", "travel_w",
        ))
        return world, Timing(
            timings("opening_ms", _integer), timings("waypoint_ms", _integer),
            timings("idle_w", _integer), timings("travel_w", _integer),
        ), _sensing(root["sensing"])
    except FixtureError:
        raise
    except (ValueError, OverflowError) as exc:
        raise FixtureError(f"invalid fixture: {exc}") from exc


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    values: dict[str, object] = {}
    for key, value in pairs:
        if key in values:
            raise FixtureError(f"duplicate fixture field: {key}")
        values[key] = value
    return values


def _record(value: object, label: str, names: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise FixtureError(f"{label} must be an object")
    obj = cast(dict[str, object], value)
    missing, unknown = set(names) - obj.keys(), obj.keys() - set(names)
    if missing or unknown:
        raise FixtureError(f"{label} fields: missing={sorted(missing)}, unknown={sorted(unknown)}")
    return obj


def _pair(value: object, label: str) -> tuple[object, object]:
    if not isinstance(value, list) or len(value) != 2:
        raise FixtureError(f"{label} must be a two-item array")
    return value[0], value[1]


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise FixtureError(f"{label} must be a string")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise FixtureError(f"{label} must be a finite number")
    return float(value)


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixtureError(f"{label} must be an integer")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise FixtureError(f"{label} must be a boolean")
    return value


def _point(value: object, label: str) -> Point:
    x, y = _pair(value, label)
    return Point(_number(x, f"{label}.x"), _number(y, f"{label}.y"))


def _room(value: object) -> Room:
    f = _Fields(value, "room", ("id", "min_corner", "max_corner"))
    return Room(f("id", _string), f("min_corner", _point), f("max_corner", _point))


def _door(value: object) -> Door:
    f = _Fields(value, "door", ("id", "rooms", "gap_start", "gap_end", "position",
                                 "jammed", "services"))
    a, b = f("rooms", _pair)
    return Door(
        f("id", _string), (_string(a, "door.rooms[0]"), _string(b, "door.rooms[1]")),
        f("gap_start", _point), f("gap_end", _point),
        DoorPosition(f("position", _string)), f("jammed", _boolean), f("services", _services),
    )


def _services(value: object, label: str) -> DoorServices:
    f = _Fields(value, label, (
        "controller_id", "controller_powered", "controller_healthy",
        "controller_data_connected", "mechanism_powered", "access_authorized", "pressure_equal",
    ))
    return DoorServices(
        f("controller_id", _string), f("controller_powered", _boolean),
        f("controller_healthy", _boolean), f("controller_data_connected", _boolean),
        f("mechanism_powered", _boolean), f("access_authorized", _boolean),
        f("pressure_equal", _boolean),
    )


def _drone(value: object) -> Drone:
    f = _Fields(value, "drone", (
        "permanent_id", "display_name", "slot", "room_id", "location", "heading_degrees",
        "capacity_wh", "charge_wh", "condition_pct", "local_dcl_signal",
        "workstation_route_available",
    ))
    return Drone(
        f("permanent_id", _string), f("display_name", _string), f("slot", _integer),
        f("room_id", _string), f("location", _point), f("heading_degrees", _number),
        f("capacity_wh", _number), f("charge_wh", _number), f("condition_pct", _number),
        f("local_dcl_signal", _boolean), f("workstation_route_available", _boolean),
    )


class _Fields:
    def __init__(self, value: object, label: str, names: tuple[str, ...]) -> None:
        self.values = _record(value, label, names)
        self.label = label

    def __call__(self, key: str, parse: Callable[[object, str], T]) -> T:
        return parse(self.values[key], f"{self.label}.{key}")


def _sensing(value: object) -> Sensing:
    fields = _Fields(value, "sensing", (
        "reach_m", "light_m", "half_angle_deg", "speed_m_s", "turn_deg_s", "body_radius_m", "markers",
    ))
    return Sensing(fields("reach_m", _number), fields("light_m", _number),
                   fields("half_angle_deg", _number), fields("speed_m_s", _number),
                   fields("turn_deg_s", _number), fields("body_radius_m", _number),
                   fields("markers", _markers))


def _markers(value: object, label: str) -> tuple[Marker, ...]:
    if not isinstance(value, list):
        raise FixtureError(f"{label} must be an array")
    result: list[Marker] = []
    for item in value:
        fields = _Fields(item, label, ("id", "point"))
        result.append(Marker(fields("id", _string), fields("point", _point)))
    return tuple(result)
