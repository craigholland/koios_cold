"""Validate reconciled manual pose segments, not continuous locomotion."""

from math import hypot

from koios_sim.domain.traversal.operation import aperture_contains, is_inside
from koios_sim.domain.traversal.world import Point, World


def validated_room(world: World, goal: Point, distance_limit_m: float,
                   opening_fraction: float, body_radius_m: float) -> str | None:
    drone = world.drone
    start = drone.location
    if hypot(goal.x_m - start.x_m, goal.y_m - start.y_m) > distance_limit_m:
        return None
    room = next((room for room in world.rooms if is_inside(room, goal)), None)
    if room is None:
        return None
    if room.id == drone.room_id:
        return room.id
    gap = world.door.gap_start
    if gap.x_m == world.door.gap_end.x_m:
        portion = (gap.x_m - start.x_m) / (goal.x_m - start.x_m)
        crossing = Point(gap.x_m, start.y_m + portion * (goal.y_m - start.y_m))
    else:
        portion = (gap.y_m - start.y_m) / (goal.y_m - start.y_m)
        crossing = Point(start.x_m + portion * (goal.x_m - start.x_m), gap.y_m)
    usable = aperture_contains(world.door, crossing, opening_fraction, body_radius_m)
    return room.id if 0 <= portion <= 1 and usable else None
