import subprocess
import sys
from dataclasses import replace

import pytest

from koios_sim.composition.fixture import load_scenario
from koios_sim.domain.traversal.operation import MJ_PER_WH, Waypoint, to_mj
from koios_sim.domain.traversal.world import DoorPosition, Point
from koios_sim.interfaces.operations import execute
from koios_sim.services.traversal.contracts import Phase, PhysicalEvent
from koios_sim.services.traversal.session import Session


def sandbox() -> Session:
    return Session(*load_scenario())


def texts(session: Session, source: str) -> list[str]:
    return [record.text for record in execute(session, source)]


def physical(
    session: Session, waypoint: Waypoint, target: str, point: Point
) -> PhysicalEvent:
    assert session.order is not None
    return PhysicalEvent(session.order.command_id, session.order.index + 1,
                         session.world.drone.permanent_id, session.stamp_ms, waypoint, target, point)


@pytest.mark.parametrize("verb", ["move", "navigate"])
def test_wait_then_separate_open_and_report_actual_arrival(verb: str) -> None:
    s = sandbox()
    assert texts(s, f"{verb} 1 M0/r2") == [
        "ACCEPTED C1: Drone 01 (1); 1 instruction(s). Previous task and queue replaced.",
        "RUNNING C1.1: Drone 01 (1); move R2.",
        "WAITING: Drone 01 (1); route blocked by D1. Open or clear the route to resume.",
    ]
    assert s.order is not None
    accepted = s.order
    assert accepted.current.drone_id == s.world.drone.permanent_id
    assert accepted.current.address == "m0/R2"
    assert texts(s, "queue show 1")[0].endswith("\n1. move m0/R2")
    assert "; action=waiting; queue=1;" in texts(s, "status all")[0]
    assert s.order is accepted
    assert texts(s, "open d1") == []
    assert s.world.door.position is DoorPosition.CLOSED
    s.advance(s.timing.opening_ms - 1)
    assert s.order is accepted and s.order.phase is Phase.WAITING
    s.advance(1)
    assert s.order is accepted and s.order.phase is Phase.RUNNING
    assert [f.text for f in s.feedback()][-2:] == [
        "OPENED: D1.", "RUNNING C1.1: Drone 01 (1); move R2."
    ]
    assert s.world.drone.room_id == "R1"

    s.advance(s.timing.waypoint_ms)
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    assert not s.report_physical(physical(s, Waypoint.BOUNDARY, "D1", Point(8, 2)))
    boundary = physical(s, Waypoint.BOUNDARY, "D1", Point(8, 3))
    assert not s.report_physical(replace(boundary, stamp_ms=s.stamp_ms - 1))
    assert not s.report_physical(replace(boundary, drone_id="other"))
    assert s.report_physical(boundary)
    assert not s.report_physical(boundary)
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    s.advance(s.timing.waypoint_ms)
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(4, 3)))
    arrival = physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3))
    assert s.report_physical(arrival)
    assert not s.report_physical(arrival)
    assert s.status().drone.room_id == "R2" and s.order is None
    result = s.feedback()
    assert result[-2].text == "ARRIVED: Drone 01 (1); room=R2."
    assert result[-1].text == "COMPLETED C1: Drone 01 (1); queue empty."
    assert result[-1].permanent_target_id == s.world.drone.permanent_id
    assert result[-1].submitted_slot == 1 and result[-1].stamp_ms == s.stamp_ms


@pytest.mark.parametrize(("source", "error"), [
    ("move 1 R2; dance", "E_UNKNOWN_COMMAND"),
    ("move 1 R2; open D1 extra", "E_USAGE"),
    ("move 1 R2; move 1 R9", "E_UNKNOWN_ID"),
    ("move 1 R2; move 2 R1", "E_SEQUENCE"),
    ("open D1; open D1", "E_SEQUENCE"),
    ("Move 1 R2", "E_UNKNOWN_COMMAND"),
    ("open other/D1", "E_UNKNOWN_ID"),
    ("move 4 R9", "E_UNKNOWN_ID"),
    ("move 4 R2", "E_SLOT"),
    ("queue show all", "E_USAGE"),
    ("context other", "E_CONTEXT"),
])
def test_invalid_input_keeps_work(source: str, error: str) -> None:
    s = sandbox()
    execute(s, "move 1 R2")
    order = s.order
    assert texts(s, source)[0].startswith(f"ERROR {error}: ")
    assert s.order is order and s.context == "m0"


def test_stop_while_waiting_cancels_automatic_resume_but_not_device() -> None:
    s = sandbox()
    execute(s, "move 1 R2")
    stale = physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3))
    execute(s, "open D1")
    assert texts(s, "stop all") == [
        "STOPPED: Drone 01 (1); current instruction cancelled and queue cleared."
    ]
    s.advance(s.timing.opening_ms)
    assert s.order is None and s.world.door.position is DoorPosition.OPEN
    execute(s, "move 1 R2")
    s.advance(s.timing.waypoint_ms)
    assert not s.report_physical(replace(stale, stamp_ms=s.stamp_ms))
    assert s.world.drone.room_id == "R1"


def test_pause_queues_and_charges_nothing_until_resumed() -> None:
    s = sandbox()
    s.set_paused(True)
    initial = s.status()
    assert texts(s, "move 1 R2") == [
        "QUEUED C1: Drone 01 (1); 1 instruction(s). Waiting for ship time to resume. "
        "Previous task and queue replaced."
    ]
    assert texts(s, "open D1") == ["QUEUED C2: D1; waiting for ship time to resume."]
    s.advance(123456)
    assert s.status() == initial
    assert s.stamp_ms == s.controller_energy_mj == s.mechanism_energy_mj == 0
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    s.set_paused(False)
    s.advance(s.timing.opening_ms)
    assert s.order is not None and s.order.phase is Phase.RUNNING
    assert s.world.door.position is DoorPosition.OPEN


@pytest.mark.parametrize(("field", "expected"), [
    ("controller_powered", "E_CONTROLLER: D1 lacks a powered functional controller."),
    ("controller_healthy", "E_CONTROLLER: D1 lacks a powered functional controller."),
    ("controller_data_connected", "E_DATA: D1 lacks a working controller data connection."),
    ("mechanism_powered", "E_POWER: D1 has no usable power for this operation."),
    ("access_authorized", "E_SECURE: Security credentials do not authorize this operation on D1."),
])
def test_open_rejects_independent_door_blockers(field: str, expected: str) -> None:
    world, timing = load_scenario()
    services = replace(world.door.services, **{field: False})
    s = Session(replace(world, door=replace(world.door, services=services)), timing)
    assert texts(s, "open D1") == [f"ERROR {expected}"]
    s.advance(100)
    assert s.world.door.position is DoorPosition.CLOSED and s.mechanism_energy_mj == 0


def test_jammed_mechanism_consumes_only_actual_attempt_energy_and_halts_queue() -> None:
    world, timing = load_scenario()
    s = Session(replace(world, door=replace(world.door, jammed=True)), timing)
    execute(s, "open D1; move 1 R2")
    s.advance(timing.opening_ms // 2)
    assert s.world.door.position is DoorPosition.CLOSED
    assert s.mechanism_energy_mj == 500 * (timing.opening_ms // 2)
    s.advance(timing.opening_ms)
    assert s.mechanism_energy_mj == 500 * timing.opening_ms
    assert s.order is not None and s.order.phase is Phase.FAILED
    assert s.feedback()[-1].text == (
        "FAILED C1.1: Drone 01 (1); E_JAMMED: D1 is jammed. "
        "Queue halted; remaining instructions retained."
    )
    assert "2. move m0/R2" in texts(s, "queue show 1")[0]


def test_accounting_is_independent_chunk_invariant_and_capped() -> None:
    a, b = sandbox(), sandbox()
    initial = to_mj(a.world.drone.charge_wh)
    for s in (a, b):
        execute(s, "move 1 R2")
        execute(s, "open D1")
    end = a.timing.opening_ms + 345
    a.advance(end)
    for ms in (100, 241, end - 341):
        b.advance(ms)
    assert a.status() == b.status()
    assert a.controller_energy_mj == b.controller_energy_mj == end * 20
    assert a.mechanism_energy_mj == b.mechanism_energy_mj == a.timing.opening_ms * 500
    assert to_mj(a.world.drone.charge_wh) == (
        initial - a.timing.idle_w * a.timing.opening_ms - a.timing.travel_w * 345
    )
    tiny = Session(replace(a.world, drone=replace(a.world.drone, charge_wh=1 / MJ_PER_WH)),
                   a.timing)
    execute(tiny, "move 1 R2")
    tiny.advance(100)
    assert tiny.world.drone.charge_wh == 0
    assert tiny.order is not None and tiny.order.phase is Phase.FAILED
    assert not tiny.report_physical(physical(tiny, Waypoint.BOUNDARY, "D1", Point(8, 3)))


def test_supported_help_and_context() -> None:
    s = sandbox()
    assert texts(s, "help") == [
        "COMMANDS Operations: context, help, move, navigate, open, queue, status, stop"
    ]
    assert texts(s, "help move")[0].startswith("USAGE: move <slot> <room>\n")
    assert "sleep" not in texts(s, "help")[0]
    assert texts(s, "context M0") == [
        "CONTEXT: m0. Camera selection does not change command context."
    ]


def test_installed_replay_uses_real_queue() -> None:
    result = subprocess.run([sys.executable, "-m", "koios_sim.composition.replay"],
                            check=True, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    wait = lines.index("WAITING: Drone 01 (1); route blocked by D1. Open or clear the route to resume.")
    opened = lines.index("OPENED: D1.")
    arrived = lines.index("ARRIVED: Drone 01 (1); room=R2.")
    completed = lines.index("COMPLETED C1: Drone 01 (1); queue empty.")
    assert wait < opened < arrived < completed


def test_device_step_runs_at_its_turn_and_stale_step_is_rejected() -> None:
    s = sandbox()
    execute(s, "open D1; move 1 R2")
    assert s.order is not None and s.order.index == 0
    assert s.world.door.position is DoorPosition.CLOSED
    s.advance(s.timing.opening_ms)
    assert s.order.index == 1 and s.world.door.position is DoorPosition.OPEN
    s.advance(s.timing.waypoint_ms)
    checkpoint = physical(s, Waypoint.BOUNDARY, "D1", Point(8, 3))
    assert not s.report_physical(replace(checkpoint, step=1))
    assert s.report_physical(checkpoint)
    s.advance(s.timing.waypoint_ms)
    assert s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    assert s.order is None


def test_already_open_steps_do_not_recurse_or_consume_mechanism_energy() -> None:
    world, timing = load_scenario()
    s = Session(replace(world, door=replace(world.door, position=DoorPosition.OPEN)), timing)
    execute(s, "; ".join(["open D1"] * 1200 + ["move 1 R2"]))
    assert s.order is not None and s.order.index == 1200
    assert s.mechanism_energy_mj == 0 and s.opening is None
