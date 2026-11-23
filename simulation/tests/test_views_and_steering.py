from dataclasses import replace

from koios_sim.composition.fixture import load_live_scenario
from koios_sim.domain.traversal.observation import observe
from koios_sim.domain.traversal.operation import Waypoint
from koios_sim.domain.traversal.world import DoorPosition, Point
from koios_sim.interfaces.bridge import Bridge
from koios_sim.interfaces.operations import execute
from koios_sim.services.traversal.contracts import PhysicalEvent
from koios_sim.services.traversal.manual_control import RoutePose
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
    assert Session(world, timing, config).snapshot().discovered_markers == ()


def test_eligible_discovery_and_controller_evidence_are_separate() -> None:
    world, timing, config = load_live_scenario()
    door = replace(world.door, services=replace(world.door.services, controller_data_connected=False))
    session = Session(replace(world, door=door), timing, config)
    initial = session.snapshot()
    assert initial.door_report is None and initial.world.door.id == "D1"
    assert initial.observation is not None and initial.observation.door_visible
    assert "M0-MARKER" not in repr(initial)

    # Headless Operations discovers a marker by changing physical heading, without a Bridge.
    d = replace(world.drone, location=Point(11, 3), room_id="R2", heading_degrees=180)
    session = Session(replace(world, drone=d, door=door), timing, config)
    assert session.snapshot().discovered_markers == ()
    assert session.begin_manual(d.permanent_id)
    lease = session.snapshot().manual_lease
    assert lease is not None
    session.advance(1300)
    assert session.report_manual(lease, d.permanent_id, 1300, d.location, 330, release=True)
    seen = session.snapshot()
    assert seen.discovered_markers == ("M0-MARKER",)
    assert seen.observation is not None
    session.update_drone_link(d.permanent_id, local_dcl=True, workstation_route=False)
    unavailable = session.snapshot()
    assert unavailable.observation is None
    assert unavailable.discovered_markers == ("M0-MARKER",)
    assert seen.observation.visible_markers[0].id == "M0-MARKER"



def test_paused_takeover_preserves_order_then_valid_takeover_invalidates_arrivals() -> None:
    session = Session(*load_live_scenario())
    execute(session, "move 1 R2")
    assert session.snapshot().active is not None
    order = session.snapshot().active
    drone = session.status().drone.permanent_id
    session.set_paused(True)
    assert not session.begin_manual(drone)
    assert session.snapshot().active == order
    session.advance(50)
    assert session.snapshot().stamp_ms == 0
    session.set_paused(False)
    assert session.begin_manual(drone)
    assert session.snapshot().active is None and session.snapshot().manual_lease is not None
    lease = session.snapshot().manual_lease
    assert lease is not None
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
    assert session.begin_manual(d.permanent_id) and session.snapshot().manual_lease
    lease = session.snapshot().manual_lease
    assert lease is not None
    session.advance(100)
    assert not session.report_manual(lease, d.permanent_id, 100, Point(8.2, 3), 0, release=False)
    opened = replace(world, door=replace(world.door, position=DoorPosition.OPEN))
    session = Session(opened, timing, sensing)
    assert session.begin_manual(d.permanent_id)
    lease = session.snapshot().manual_lease
    assert lease is not None
    session.advance(100)
    assert session.report_manual(lease, d.permanent_id, 100, Point(8.2, 3), 0, release=False)
    assert session.status().drone.room_id == "R2"


def test_stale_manual_cycle_has_no_time_or_charge_side_effect() -> None:
    session = Session(*load_live_scenario())
    bridge = Bridge(session, "local")
    bridge.handle({"kind": "hello", "seq": 1, "version": 1, "nonce": "local"})
    d = session.status().drone
    bridge.handle({"kind": "manual_begin", "seq": 2, "drone_id": d.permanent_id})
    assert session.snapshot().manual_lease is not None
    before = session.status().drone.charge_wh
    result = bridge.handle({
        "kind": "manual_cycle", "seq": 3, "lease_id": "stale", "drone_id": d.permanent_id,
        "stamp_ms": 0, "elapsed_ms": 100, "x_m": 4, "y_m": 3, "heading": 0, "release": False,
    })
    assert result["note"] == "Direct motion was not confirmed."
    assert session.snapshot().stamp_ms == 0 and session.status().drone.charge_wh == before


def test_handoff_validates_old_order_and_commits_pose_before_cancelling() -> None:
    world, timing, sensing = load_live_scenario()
    world = replace(world, door=replace(world.door, position=DoorPosition.OPEN))
    session = Session(world, timing, sensing)
    execute(session, "move 1 R2")
    old = session.snapshot().active
    assert old is not None
    session.advance(250)
    accepted = session.snapshot().active
    actual = RoutePose(old.command_id, 1, 250, 30, Point(5.35, 3), 0)
    assert not session.begin_manual(world.drone.permanent_id, replace(actual, command_id="stale"))
    assert not session.begin_manual(world.drone.permanent_id, replace(actual, stamp_ms=249))
    assert not session.begin_manual(world.drone.permanent_id, replace(actual, point=Point(7, 3)))
    assert session.snapshot().stamp_ms == 250 and session.snapshot().active == accepted
    assert session.begin_manual(world.drone.permanent_id, actual)
    assert session.status().drone.location == actual.point and session.snapshot().stamp_ms == 280
    assert session.snapshot().active is None and session.snapshot().manual_lease is not None
    assert not session.report_physical(PhysicalEvent(old.command_id, 1, world.drone.permanent_id,
                                                     280, Waypoint.ARRIVAL, "R2", Point(12, 3)))


def test_manual_aperture_uses_circular_body_width_during_opening() -> None:
    world, timing, sensing = load_live_scenario()
    d = replace(world.drone, location=Point(7.9, 3))
    session = Session(replace(world, drone=d), timing, sensing)
    execute(session, "open D1")
    assert session.begin_manual(d.permanent_id) and session.snapshot().manual_lease is not None
    lease = session.snapshot().manual_lease
    assert lease is not None
    session.advance(300)
    assert not session.report_manual(lease, d.permanent_id, 300, Point(8.1, 3), 0, release=False)
    session.advance(400)
    assert session.status().door.position is DoorPosition.CLOSED
    assert not session.report_manual(lease, d.permanent_id, 700, Point(8.1, 3.5), 0, release=False)
    assert session.report_manual(lease, d.permanent_id, 700, Point(8.1, 3), 0, release=True)
    assert session.status().drone.room_id == "R2"


def test_autonomous_samples_gate_python_sensing_and_respect_active_order() -> None:
    world, timing, sensing = load_live_scenario()
    world = replace(world, door=replace(world.door, position=DoorPosition.OPEN))
    session = Session(world, timing, sensing)
    execute(session, "move 1 R2")
    order = session.snapshot().active
    assert order is not None
    route = RoutePose(order.command_id, 1, 0, 100, Point(4.5, 3), 0)
    assert not session.report_route_pose(replace(route, step=2))
    assert not session.report_route_pose(replace(route, point=Point(8.3, 3)))
    assert session.snapshot().stamp_ms == 0
    assert session.report_route_pose(route)
    assert session.snapshot().active == order and session.status().drone.location == route.point
    assert not session.report_route_pose(route)
    assert not session.report_route_pose(replace(route, stamp_ms=100, point=Point(5.5, 3)))
    observation = session.snapshot().observation
    assert observation is not None
    assert observation.polygon[0] == route.point and observation.visible_markers == ()
    assert session.snapshot().stamp_ms == 100 and session.snapshot().active == order
    assert not any("ARRIVED" in record.text for record in session.feedback())
