"""Bounded fixture sensing: forward light, room walls, and actual D1 aperture."""

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin

from koios_sim.domain.traversal.operation import aperture_contains
from koios_sim.domain.traversal.world import Point, Room, World


@dataclass(frozen=True, slots=True)
class Marker:
    id: str
    point: Point


@dataclass(frozen=True, slots=True)
class Sensing:
    reach_m: float
    light_m: float
    half_angle_deg: float
    speed_m_s: float
    turn_deg_s: float
    body_radius_m: float
    markers: tuple[Marker, ...]

    def __post_init__(self) -> None:
        if min(self.reach_m, self.light_m, self.speed_m_s, self.turn_deg_s, self.body_radius_m) <= 0:
            raise ValueError("provisional sensing and steering values must be positive")
        if not 0 < self.half_angle_deg < 90:
            raise ValueError("sensing half-angle must be strictly between 0 and 90 degrees")
        if len({marker.id for marker in self.markers}) != len(self.markers):
            raise ValueError("provisional observation marker IDs must be distinct")


@dataclass(frozen=True, slots=True)
class Observation:
    polygon: tuple[Point, ...]
    door_visible: bool
    visible_markers: tuple[Marker, ...]


def observe(world: World, profile: Sensing, opening: float) -> Observation:
    d = world.drone
    origin = d.location
    room = next(room for room in world.rooms if room.id == d.room_id)
    other = next(candidate for candidate in world.rooms if candidate.id != room.id)
    reach = min(profile.reach_m, profile.light_m)

    def extent(angle: float) -> Point:
        dx, dy = cos(radians(angle)), sin(radians(angle))
        walls = _exit_distance(room, origin, dx, dy)
        if aperture_contains(
            world.door, Point(origin.x_m + walls * dx, origin.y_m + walls * dy), opening, 0.0
        ):
            walls = _exit_distance(other, origin, dx, dy)
        return Point(origin.x_m + min(reach, walls) * dx, origin.y_m + min(reach, walls) * dy)

    def visible(point: Point) -> bool:
        dx, dy = point.x_m - origin.x_m, point.y_m - origin.y_m
        angle = degrees(atan2(dy, dx))
        offset = (angle - d.heading_degrees + 180) % 360 - 180
        if abs(offset) > profile.half_angle_deg:
            return False
        edge = extent(angle)
        return hypot(dx, dy) <= hypot(edge.x_m - origin.x_m, edge.y_m - origin.y_m) + 1e-7

    a, b = world.door.gap_start, world.door.gap_end
    door_visible = visible(Point((a.x_m + b.x_m) / 2, (a.y_m + b.y_m) / 2))
    fan = tuple(extent(d.heading_degrees + profile.half_angle_deg * (index / 12 - 1))
                for index in range(25))
    return Observation((origin, *fan), door_visible,
                       tuple(marker for marker in profile.markers if visible(marker.point)))


def _exit_distance(room: Room, p: Point, dx: float, dy: float) -> float:
    right = (room.max_corner.x_m - p.x_m) / dx if dx > 0 else (
        (room.min_corner.x_m - p.x_m) / dx if dx < 0 else float("inf")
    )
    bottom = (room.max_corner.y_m - p.y_m) / dy if dy > 0 else (
        (room.min_corner.y_m - p.y_m) / dy if dy < 0 else float("inf")
    )
    return min(right, bottom)
