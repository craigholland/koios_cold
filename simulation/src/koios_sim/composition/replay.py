"""Developer replay of the real M0 semantic boundary, not a physics simulation."""

from koios_sim.composition.fixture import load_scenario
from koios_sim.domain.traversal.operation import Waypoint
from koios_sim.domain.traversal.world import Point
from koios_sim.interfaces.operations import execute
from koios_sim.services.traversal.contracts import PhysicalEvent
from koios_sim.services.traversal.session import Session


def main() -> int:
    world, timing = load_scenario()
    session = Session(world, timing)
    execute(session, "move 1 R2; open D1", origin="developer")
    execute(session, "status 1", origin="developer")
    execute(session, "queue show 1", origin="developer")
    execute(session, "open D1", origin="developer")
    session.advance(timing.opening_ms)
    order = session.order
    if order is None:
        raise RuntimeError("the destination should still be active")
    gap_a, gap_b = world.door.gap_start, world.door.gap_end
    room_a, room_b = world.rooms[1].min_corner, world.rooms[1].max_corner
    for waypoint, target, location in (
        (Waypoint.BOUNDARY, world.door.id,
         Point((gap_a.x_m + gap_b.x_m) / 2, (gap_a.y_m + gap_b.y_m) / 2)),
        (Waypoint.ARRIVAL, world.rooms[1].id,
         Point((room_a.x_m + room_b.x_m) / 2, (room_a.y_m + room_b.y_m) / 2)),
    ):
        session.advance(timing.waypoint_ms)
        if not session.report_physical(PhysicalEvent(
            order.command_id, 1, world.drone.permanent_id, session.stamp_ms, waypoint,
            target, location,
        )):
            raise RuntimeError(f"developer report rejected: {waypoint}")
    execute(session, "status all", origin="developer")
    for record in session.feedback():
        print(record.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
