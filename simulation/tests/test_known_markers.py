"""The application exposes known static positions only after confirmed observation."""

from dataclasses import FrozenInstanceError, replace

import pytest

from koios_sim.composition.fixture import load_live_scenario
from koios_sim.domain.traversal.world import Point
from koios_sim.interfaces.live_snapshot import encode_snapshot
from koios_sim.services.traversal.session import Session


@pytest.mark.parametrize(("dcl", "route"), [(False, True), (True, False)])
def test_known_markers_survive_lost_sensing_but_are_not_leaked_to_new_session(
    dcl: bool, route: bool,
) -> None:
    world, timing, sensing = load_live_scenario()
    drone = replace(world.drone, location=Point(11, 3), room_id="R2", heading_degrees=180)
    world = replace(world, drone=drone)
    session = Session(world, timing, sensing)
    unseen = session.snapshot()
    assert unseen.observation is not None and unseen.observation.visible_markers == ()
    assert unseen.discovered_markers == unseen.known_markers == ()
    blank = encode_snapshot(unseen)
    assert blank["known_markers"] == [] and "M0-MARKER" not in repr(blank)

    assert session.begin_manual(drone.permanent_id)
    lease = session.snapshot().manual_lease
    assert lease is not None
    session.advance(1300)
    assert session.report_manual(lease, drone.permanent_id, 1300, drone.location, 330, release=False)
    observed = session.snapshot()
    assert observed.observation is not None
    assert observed.known_markers == observed.observation.visible_markers == sensing.markers
    marker, = observed.known_markers
    with pytest.raises(FrozenInstanceError):
        setattr(marker, "point", Point(0, 0))

    session.advance(1300)
    assert session.report_manual(lease, drone.permanent_id, 2600, drone.location, 180, release=True)
    away = session.snapshot()
    assert away.observation is not None and away.observation.visible_markers == ()
    assert away.discovered_markers == (marker.id,) and away.known_markers == (marker,)
    session.update_drone_link(drone.permanent_id, local_dcl=dcl, workstation_route=route)
    lost = session.snapshot()
    records = session.feedback()
    assert lost.observation is None and lost.known_markers == (marker,)
    for _ in range(2):
        wire = encode_snapshot(session.snapshot())
        assert wire["sensor"] is None and wire["discovered_markers"] == [marker.id]
        assert wire["known_markers"] == [
            {"id": marker.id, "point": {"x_m": marker.point.x_m, "y_m": marker.point.y_m}},
        ]
        wire["known_markers"].clear()
        assert session.snapshot() == lost and session.feedback() == records
    assert Session(world, timing, sensing).snapshot() == unseen
