"""Deterministic M0 traversal predicates and resource accounting."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from koios_sim.domain.traversal.world import Door, DoorPosition, Point, Room

MJ_PER_WH = 3_600_000
CONTROLLER_W = 20
DOOR_MECHANISM_W = 500


@dataclass(frozen=True, slots=True)
class Timing:
    opening_ms: int
    waypoint_ms: int
    idle_w: int
    travel_w: int

    def __post_init__(self) -> None:
        if min(self.opening_ms, self.waypoint_ms, self.idle_w) <= 0:
            raise ValueError("fixture timings and idle power must be positive")
        if self.travel_w < self.idle_w:
            raise ValueError("fixture travel power must be at least idle power")


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    reason: str


class Waypoint(StrEnum):
    BOUNDARY = "boundary"
    ARRIVAL = "arrival"


def door_failure(door: Door) -> Failure | None:
    facts = door.services
    if not facts.access_authorized:
        return Failure("E_SECURE", f"Security credentials do not authorize this operation on {door.id}.")
    if not facts.controller_powered or not facts.controller_healthy:
        return Failure("E_CONTROLLER", f"{door.id} lacks a powered functional controller.")
    if not facts.controller_data_connected:
        return Failure("E_DATA", f"{door.id} lacks a working controller data connection.")
    if not facts.mechanism_powered:
        return Failure("E_POWER", f"{door.id} has no usable power for this operation.")
    if door.jammed:
        return Failure("E_JAMMED", f"{door.id} is jammed.")
    return None


def can_cross(door: Door, point: Point) -> bool:
    return aperture_contains(door, point, float(door.position is DoorPosition.OPEN), 0.0)


def aperture_contains(door: Door, point: Point, fraction: float, radius_m: float) -> bool:
    """A circular body must fit between the two leaf edges at the shared wall."""
    a, b = door.gap_start, door.gap_end
    if a.x_m == b.x_m:
        if abs(point.x_m - a.x_m) > 1e-7:
            return False
        lo, hi, coordinate = a.y_m, b.y_m, point.y_m
    else:
        if abs(point.y_m - a.y_m) > 1e-7:
            return False
        lo, hi, coordinate = a.x_m, b.x_m, point.x_m
    half_open = (hi - lo) * fraction / 2
    return radius_m + abs(coordinate - (lo + hi) / 2) < half_open

def is_inside(room: Room, point: Point) -> bool:
    a, b = room.min_corner, room.max_corner
    return a.x_m < point.x_m < b.x_m and a.y_m < point.y_m < b.y_m


def to_mj(wh: float) -> int:
    return int((Decimal(str(wh)) * MJ_PER_WH).to_integral_value(rounding=ROUND_HALF_UP))


def spend(charge_wh: float, power_w: int, elapsed_ms: int) -> float:
    return min(charge_wh, max(0, to_mj(charge_wh) - power_w * elapsed_ms) / MJ_PER_WH)
