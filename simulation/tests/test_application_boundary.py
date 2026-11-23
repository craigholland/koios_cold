"""Application ownership, immutable reads, and compatible wire timing."""

from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock

import pytest

from koios_sim.composition.fixture import load_live_scenario, load_scenario
from koios_sim.domain.traversal.operation import MJ_PER_WH, to_mj
from koios_sim.domain.traversal.world import DoorPosition
from koios_sim.interfaces.bridge import Bridge, MessageError
from koios_sim.interfaces.live_snapshot import encode_snapshot
from koios_sim.interfaces.operations import execute
from koios_sim.services.traversal.contracts import Phase, Request, Verb
from koios_sim.services.traversal.session import Session


def _hello(bridge: Bridge) -> dict[str, object]:
    return bridge.handle({"kind": "hello", "seq": 1, "version": 1, "nonce": "local"})


def test_bridge_delegates_to_application_surface_and_maps_a_detached_result() -> None:
    real = Session(*load_live_scenario())
    application = Mock(spec_set=Session, wraps=real)
    bridge = Bridge(application, "local")
    _hello(bridge)
    result = bridge.handle({"kind": "command", "seq": 2, "text": "move 1 R2"})
    application.submit.assert_called_once_with((Request(Verb.MOVE, ("1", "R2")),), "godot")
    assert application.snapshot.call_count == 2
    assert result["state"]["active"]["phase"] == "waiting"
    assert result["kind"] == "snapshot" and result["seq"] == 2

    tick = bridge.handle({"kind": "tick", "seq": 3, "elapsed_ms": 20})
    application.apply_tick.assert_called_once_with(20, None)
    assert tick["state"]["stamp_ms"] == 20
    assert tick["feedback"] == []


def test_snapshot_inspection_and_serialization_never_mutate_work_or_discovery() -> None:
    session = Session(*load_live_scenario())
    execute(session, "move 1 R2; open D1")
    captured = session.snapshot()
    order = captured.active
    assert order is not None and order.phase is Phase.WAITING and len(order.remaining) == 2

    with pytest.raises(FrozenInstanceError):
        setattr(order, "remaining", ())
    with pytest.raises(FrozenInstanceError):
        setattr(captured.world.drone, "charge_wh", 0)

    before = session.feedback()
    expected = encode_snapshot(captured)
    for _ in range(2):
        projected = encode_snapshot(session.snapshot())
        assert projected == expected
        projected["active"]["phase"] = "changed only in the detached wire dictionary"
        assert session.snapshot() == captured and session.feedback() == before
    execute(session, "queue show 1")
    execute(session, "status all")
    assert session.snapshot() == captured
    assert len(session.feedback()) == len(before) + 2

    execute(session, "open D1")
    session.advance(session.timing.opening_ms)
    active = session.snapshot().active
    assert active is not None and active.phase is Phase.RUNNING
    assert order.phase is Phase.WAITING and captured.world.door.position is DoorPosition.CLOSED
    assert encode_snapshot(captured) == expected


def test_v1_wire_shape_and_optional_presentation_group_are_unchanged() -> None:
    headless = _hello(Bridge(Session(*load_scenario()), "local"))
    live = _hello(Bridge(Session(*load_live_scenario()), "local"))
    assert set(live) == set(headless) == {"kind", "seq", "note", "state", "feedback"}
    assert live["kind"] == "snapshot" and live["seq"] == 1
    assert live["note"] is None and live["feedback"] == []
    core = {"world", "stamp_ms", "paused", "opening_fraction", "door_activity",
            "door_energy_mj", "active", "manual"}
    assert set(headless["state"]) == core
    data = live["state"]
    assert set(data) == core | {
        "door_report", "sensor", "discovered_markers", "known_markers", "steering", "completion",
    }
    assert data["door_report"] == {"position": "closed", "stamp_ms": 0, "source": "controller"}
    assert set(data["sensor"]) == {"polygon", "door_visible", "visible_markers"}
    assert data["discovered_markers"] == [] and data["known_markers"] == []
    assert set(data["steering"]) == {"speed_m_s", "turn_deg_s", "body_radius_m"}
    assert data["completion"] == {
        "verbs": ["context", "help", "move", "navigate", "open", "queue", "status", "stop"],
        "deck": "m0", "slot": "1", "rooms": ["R1", "R2"], "doors": ["D1"],
    }


def test_manual_admission_preserves_error_order_ack_and_elapsed_accounting() -> None:
    session = Session(*load_live_scenario())
    bridge = Bridge(session, "local")
    _hello(bridge)
    drone_id = session.status().drone.permanent_id
    granted = bridge.handle({"kind": "manual_begin", "seq": 2, "drone_id": drone_id})
    lease = granted["state"]["manual"]
    before = session.snapshot()
    cycle = {"kind": "manual_cycle", "seq": 3, "lease_id": lease, "drone_id": drone_id,
             "x_m": 12.0, "y_m": 3.0, "heading": 0.0, "release": False}
    malformed = {**cycle, "stamp_ms": "bad", "elapsed_ms": "bad"}
    stale = bridge.handle({**malformed, "lease_id": "earlier"})
    assert stale["seq"] == 3 and stale["note"] == "Direct motion was not confirmed."
    assert session.snapshot() == before
    with pytest.raises(MessageError, match="stamp_ms must be an integer >= 0"):
        bridge.handle({**malformed, "seq": 4})
    with pytest.raises(MessageError, match="elapsed_ms must be an integer >= 0"):
        bridge.handle({**malformed, "seq": 4, "stamp_ms": 0})
    with pytest.raises(MessageError, match="tick exceeds the dev interval limit"):
        bridge.handle({**cycle, "seq": 4, "stamp_ms": 0, "elapsed_ms": 251})
    assert session.snapshot() == before

    unconfirmed = bridge.handle({**cycle, "seq": 4, "stamp_ms": 0, "elapsed_ms": 100})
    assert unconfirmed["seq"] == 4 and unconfirmed["note"] == "Direct motion was not confirmed."
    after = session.snapshot()
    assert after.stamp_ms == 100 and after.world.drone.location == before.world.drone.location
    assert to_mj(before.world.drone.charge_wh) - to_mj(after.world.drone.charge_wh) == (
        100 * session.timing.travel_w
    )
    stale = bridge.handle({**cycle, "seq": 5, "stamp_ms": 0, "elapsed_ms": "ignored"})
    assert stale["seq"] == 5 and stale["note"] == "Direct motion was not confirmed."
    assert session.snapshot() == after


@pytest.mark.parametrize("exhausted", [False, True])
def test_route_fallback_advances_once_before_or_after_reconciliation(exhausted: bool) -> None:
    world, timing, sensing = load_live_scenario()
    available = 3 * timing.travel_w if exhausted else to_mj(world.drone.charge_wh)
    drone = replace(world.drone, charge_wh=available / MJ_PER_WH)
    world = replace(world, door=replace(world.door, position=DoorPosition.OPEN), drone=drone)
    session = Session(world, timing, sensing)
    bridge = Bridge(session, "local")
    _hello(bridge)
    active = bridge.handle({"kind": "command", "seq": 2, "text": "move 1 R2"})["state"]["active"]
    pose = {"command_id": active["command_id"], "step": 1, "stamp_ms": 0, "elapsed_ms": 10,
            "x_m": 4 if exhausted else 7, "y_m": 3, "heading": 0}
    with pytest.raises(MessageError, match="pose interval must match tick interval"):
        bridge.handle({"kind": "tick", "seq": 3, "elapsed_ms": 11, "route_pose": pose})
    assert session.snapshot().stamp_ms == 0
    result = bridge.handle({"kind": "tick", "seq": 3, "elapsed_ms": 10, "route_pose": pose})
    now = session.snapshot()
    assert result["seq"] == 3 and now.stamp_ms == 10 and now.controller_energy_mj == 200
    assert now.world.drone.location == drone.location
    assert now.active is not None
    if exhausted:
        assert now.active.phase is Phase.FAILED
        assert to_mj(now.world.drone.charge_wh) == 0
        assert result["feedback"][0]["stamp_ms"] == 3 and "E_POWER" in result["feedback"][0]["text"]
    else:
        assert now.active.phase is Phase.RUNNING
        assert to_mj(now.world.drone.charge_wh) == available - 10 * timing.travel_w
        assert result["feedback"] == []
