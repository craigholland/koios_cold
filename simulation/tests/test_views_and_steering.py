from dataclasses import replace

from koios_sim.composition.fixture import load_live_scenario
from koios_sim.domain.traversal.observation import observe
from koios_sim.domain.traversal.operation import Waypoint
from koios_sim.domain.traversal.world import DoorPosition, Point
from koios_sim.interfaces.bridge import Bridge, _presentation
from koios_sim.interfaces.operations import execute
from koios_sim.services.traversal.contracts import PhysicalEvent
from koios_sim.services.traversal.session import Session


def test_sensing_does_not_expose_room_contents_on_entry() -> None:
    world, timing, config = load_live_scenario()
    result = observe(world, config, 0.0)
    assert result.door_visible and result.visible_markers == ()
    near = replace(world, drone=replace(world.drone, location=Point(7, 3)))
    assert max(point.x_m for point in observe(near, config, 0).polygon) <= 8.0
    assert max(point.x_m for point in observe(near, config, 1).polygon) > 8.0
    # Entering R2 says nothing about its contents while looking away.
    interior = replace(world.drone, room_id="R2", location=Point(11, 3), heading_degrees=180)
    current = replace(world, drone=interior)
    assert observe(current, config, 1).visible_markers == ()
    aimed = replace(current, drone=replace(interior, heading_degrees=330))
    assert [m.id for m in observe(aimed, config, 1).visible_markers] == ["M0-MARKER"]
    dark = replace(config, light_m=1)
    assert observe(aimed, dark, 1).visible_markers == ()
    assert Session(world, timing, config).discovered_markers == set()


def test_eligible_discovery_and_controller_evidence_are_separate() -> None:
    world, timing, config = load_live_scenario()
    door = replace(world.door, services=replace(world.door.services, controller_data_connected=False))
    session = Session(replace(world, door=door), timing, config)
    initial = _presentation(session, 0)
    assert initial["door_report"] is None
    assert initial["completion"]["doors"] == ["D1"]
    assert initial["sensor"]["door_visible"]
    assert "M0-MARKER" not in repr(initial)
    d = replace(world.drone, location=Point(11, 3), room_id="R2", heading_degrees=330)
    session.world = replace(session.world, drone=d)
    assert _presentation(session, 0)["discovered_markers"] == ["M0-MARKER"]
    session.world = replace(session.world, drone=replace(d, workstation_route_available=False))
    unavailable = _presentation(session, 0)
    assert unavailable["sensor"] is None
    assert unavailable["discovered_markers"] == ["M0-MARKER"]
    assert "M0-MARKER" not in repr(unavailable["completion"])


def test_paused_takeover_preserves_order_then_valid_takeover_invalidates_arrivals() -> None:
    session = Session(*load_live_scenario())
    execute(session, "move 1 R2")
    assert session.order is not None
    order = session.order
    drone = session.world.drone.permanent_id
    session.set_paused(True)
    assert not session.begin_manual(drone)
    assert session.order is order
    session.advance(50)
    assert session.stamp_ms == 0
    session.set_paused(False)
    assert session.begin_manual(drone)
    assert session.order is None and session.manual is not None
    lease = session.manual.id
    session.advance(100)
    assert not session.report_physical(PhysicalEvent(order.command_id, 1, drone, 100,
                                                     Waypoint.ARRIVAL, "R2", Point(12, 3)))
    assert not session.report_manual(lease, drone, 100, Point(12, 3), 0, release=False)
    assert session.report_manual(lease, drone, 100, Point(4.3, 3), 0, release=True)
    assert session.status().drone.location == Point(4.3, 3)
    assert not session.report_manual(lease, drone, 100, Point(4.3, 3), 0, release=True)


def test_manual_crossing_is_blocked_at_closed_door_even_with_enough_elapsed() -> None:
    world, timing, sensing = load_live_scenario()
    d = replace(world.drone, location=Point(7.9, 3))
    world = replace(world, drone=d)
    session = Session(world, timing, sensing)
    assert session.begin_manual(d.permanent_id) and session.manual
    lease = session.manual.id
    session.advance(100)
    assert not session.report_manual(lease, d.permanent_id, 100, Point(8.2, 3), 0, release=False)
    session.world = replace(world, door=replace(world.door, position=DoorPosition.OPEN))
    assert session.report_manual(lease, d.permanent_id, 100, Point(8.2, 3), 0, release=False)
    assert session.status().drone.room_id == "R2"


def test_stale_manual_cycle_has_no_time_or_charge_side_effect() -> None:
    session = Session(*load_live_scenario())
    bridge = Bridge(session, "local")
    bridge.handle({"kind": "hello", "seq": 1, "version": 1, "nonce": "local"})
    d = session.world.drone
    bridge.handle({"kind": "manual_begin", "seq": 2, "drone_id": d.permanent_id})
    assert session.manual is not None
    before = session.world.drone.charge_wh
    result = bridge.handle({
        "kind": "manual_cycle", "seq": 3, "lease_id": "stale", "drone_id": d.permanent_id,
        "stamp_ms": 0, "elapsed_ms": 100, "x_m": 4, "y_m": 3, "heading": 0, "release": False,
    })
    assert result["note"] == "Direct motion was not confirmed."
    assert session.stamp_ms == 0 and session.world.drone.charge_wh == before
