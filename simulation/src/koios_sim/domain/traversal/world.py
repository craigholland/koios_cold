"""Entities and consistency rules for the bounded traversal fixture."""

import re
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


@dataclass(frozen=True, slots=True)
class Point:
    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        if not isfinite(self.x_m) or not isfinite(self.y_m):
            raise ValueError("geometry coordinates must be finite")


@dataclass(frozen=True, slots=True)
class Room:
    id: str
    min_corner: Point
    max_corner: Point

    def __post_init__(self) -> None:
        _identifier(self.id, r"R[1-9][0-9]*", "room ID")
        if (
            self.min_corner.x_m >= self.max_corner.x_m
            or self.min_corner.y_m >= self.max_corner.y_m
        ):
            raise ValueError(f"{self.id} must have positive floor area")


class DoorPosition(StrEnum):
    CLOSED = "closed"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class DoorServices:
    controller_id: str
    controller_powered: bool
    controller_healthy: bool
    controller_data_connected: bool
    mechanism_powered: bool
    access_authorized: bool
    pressure_equal: bool

    def __post_init__(self) -> None:
        _identifier(self.controller_id, r"[a-z0-9]+(?:-[a-z0-9]+)*", "controller ID")


@dataclass(frozen=True, slots=True)
class Door:
    id: str
    rooms: tuple[str, str]
    gap_start: Point
    gap_end: Point
    position: DoorPosition
    jammed: bool
    services: DoorServices

    def __post_init__(self) -> None:
        _identifier(self.id, r"D[1-9][0-9]*", "door ID")
        if self.rooms[0] == self.rooms[1]:
            raise ValueError(f"{self.id} must connect distinct rooms")
        if not (
            (self.gap_start.x_m == self.gap_end.x_m
             and self.gap_start.y_m < self.gap_end.y_m)
            or (self.gap_start.y_m == self.gap_end.y_m
                and self.gap_start.x_m < self.gap_end.x_m)
        ):
            raise ValueError(f"{self.id} needs an ordered axis-aligned opening")


@dataclass(frozen=True, slots=True)
class Drone:
    permanent_id: str
    display_name: str
    slot: int
    room_id: str
    location: Point
    heading_degrees: float
    capacity_wh: float
    charge_wh: float
    condition_pct: float
    local_dcl_signal: bool
    workstation_route_available: bool

    def __post_init__(self) -> None:
        _identifier(self.permanent_id, r"[a-z0-9]+(?:-[a-z0-9]+)*", "permanent drone ID")
        if not self.display_name.strip():
            raise ValueError("drone display name must not be empty")
        if self.slot < 1:
            raise ValueError("assigned drone slot must be positive")
        if not (
            isfinite(self.capacity_wh)
            and self.capacity_wh > 0
            and 0 <= self.charge_wh <= self.capacity_wh
        ):
            raise ValueError("drone charge must be between zero and positive capacity")
        if not 0 <= self.condition_pct <= 100:
            raise ValueError("drone condition must be between 0 and 100 percent")
        if not 0 <= self.heading_degrees < 360:
            raise ValueError("drone heading must be in [0, 360) degrees")


@dataclass(frozen=True, slots=True)
class World:
    deck_id: str
    rooms: tuple[Room, Room]
    door: Door
    drone: Drone

    def __post_init__(self) -> None:
        _identifier(self.deck_id, r"[a-z][a-z0-9]*", "deck ID")
        rooms = {room.id: room for room in self.rooms}
        if len(rooms) != len(self.rooms):
            raise ValueError("duplicate room ID")
        if set(self.door.rooms) != rooms.keys():
            raise ValueError(f"{self.door.id} endpoints must identify both fixture rooms")
        if self.drone.room_id not in rooms:
            raise ValueError("drone references an unknown room")
        a, b = self.rooms
        if (
            max(a.min_corner.x_m, b.min_corner.x_m) < min(a.max_corner.x_m, b.max_corner.x_m)
            and max(a.min_corner.y_m, b.min_corner.y_m) < min(a.max_corner.y_m, b.max_corner.y_m)
        ):
            raise ValueError("room floors must not overlap")
        if not all(_on_wall(room, self.door.gap_start, self.door.gap_end) for room in self.rooms):
            raise ValueError(f"{self.door.id} opening must lie on both rooms' shared wall")
        room = rooms[self.drone.room_id]
        p = self.drone.location
        if not (
            room.min_corner.x_m < p.x_m < room.max_corner.x_m
            and room.min_corner.y_m < p.y_m < room.max_corner.y_m
        ):
            raise ValueError("drone must start inside its referenced room")


def _identifier(value: str, pattern: str, name: str) -> None:
    if not re.fullmatch(pattern, value):
        raise ValueError(f"invalid {name}: {value!r}")


def _on_wall(room: Room, start: Point, end: Point) -> bool:
    lo, hi = room.min_corner, room.max_corner
    if start.x_m == end.x_m:
        return start.x_m in (lo.x_m, hi.x_m) and lo.y_m <= start.y_m < end.y_m <= hi.y_m
    return start.y_m in (lo.y_m, hi.y_m) and lo.x_m <= start.x_m < end.x_m <= hi.x_m
