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
    assert session.snapshot().active is not None
    return PhysicalEvent(session.snapshot().active.command_id, session.snapshot().active.step,
                         session.status().drone.permanent_id, session.snapshot().stamp_ms, waypoint, target, point)


@pytest.mark.parametrize("verb", ["move", "navigate"])
def test_wait_then_separate_open_and_report_actual_arrival(verb: str) -> None:
    s = sandbox()
    assert texts(s, f"{verb} 1 M0/r2") == [
        "ACCEPTED C1: Drone 01 (1); 1 instruction(s). Previous task and queue replaced.",
        "RUNNING C1.1: Drone 01 (1); move R2.",
        "WAITING: Drone 01 (1); route blocked by D1. Open or clear the route to resume.",
    ]
    assert s.snapshot().active is not None
    accepted = s.snapshot().active
    assert accepted.current.drone_id == s.status().drone.permanent_id
    assert accepted.current.address == "m0/R2"
    assert texts(s, "queue show 1")[0].endswith("\n1. move m0/R2")
    assert "; action=waiting; queue=1;" in texts(s, "status all")[0]
    assert s.snapshot().active == accepted
    assert texts(s, "open d1") == []
    assert s.status().door.position is DoorPosition.CLOSED
    s.advance(s.timing.opening_ms - 1)
    assert s.snapshot().active.command_id == accepted.command_id and s.snapshot().active.phase is Phase.WAITING
    s.advance(1)
    assert s.snapshot().active.command_id == accepted.command_id and s.snapshot().active.phase is Phase.RUNNING
    assert [f.text for f in s.feedback()][-2:] == [
        "OPENED: D1.", "RUNNING C1.1: Drone 01 (1); move R2."
    ]
    assert s.status().drone.room_id == "R1"

    s.advance(s.timing.waypoint_ms)
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    assert not s.report_physical(physical(s, Waypoint.BOUNDARY, "D1", Point(8, 2)))
    boundary = physical(s, Waypoint.BOUNDARY, "D1", Point(8, 3))
    assert not s.report_physical(replace(boundary, stamp_ms=s.snapshot().stamp_ms - 1))
    assert not s.report_physical(replace(boundary, drone_id="other"))
    assert s.report_physical(boundary)
    assert not s.report_physical(boundary)
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    s.advance(s.timing.waypoint_ms)
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(4, 3)))
    arrival = physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3))
    assert s.report_physical(arrival)
    assert not s.report_physical(arrival)
    assert s.status().drone.room_id == "R2" and s.snapshot().active is None
    result = s.feedback()
    assert result[-2].text == "ARRIVED: Drone 01 (1); room=R2."
    assert result[-1].text == "COMPLETED C1: Drone 01 (1); queue empty."
    assert result[-1].permanent_target_id == s.status().drone.permanent_id
    assert result[-1].submitted_slot == 1 and result[-1].stamp_ms == s.snapshot().stamp_ms


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
    order = s.snapshot().active
    assert texts(s, source)[0].startswith(f"ERROR {error}: ")
    assert s.snapshot().active == order and s.snapshot().context == "m0"


def test_stop_while_waiting_cancels_automatic_resume_but_not_device() -> None:
    s = sandbox()
    execute(s, "move 1 R2")
    stale = physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3))
    execute(s, "open D1")
    assert texts(s, "stop all") == [
        "STOPPED: Drone 01 (1); current instruction cancelled and queue cleared."
    ]
    s.advance(s.timing.opening_ms)
    assert s.snapshot().active is None and s.status().door.position is DoorPosition.OPEN
    execute(s, "move 1 R2")
    s.advance(s.timing.waypoint_ms)
    assert not s.report_physical(replace(stale, stamp_ms=s.snapshot().stamp_ms))
    assert s.status().drone.room_id == "R1"


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
    assert s.snapshot().stamp_ms == s.snapshot().controller_energy_mj == s.snapshot().mechanism_energy_mj == 0
    assert not s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    s.set_paused(False)
    s.advance(s.timing.opening_ms)
    assert s.snapshot().active is not None and s.snapshot().active.phase is Phase.RUNNING
    assert s.status().door.position is DoorPosition.OPEN


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
    assert s.status().door.position is DoorPosition.CLOSED and s.snapshot().mechanism_energy_mj == 0


def test_jammed_mechanism_consumes_only_actual_attempt_energy_and_halts_queue() -> None:
    world, timing = load_scenario()
    s = Session(replace(world, door=replace(world.door, jammed=True)), timing)
    execute(s, "open D1; move 1 R2")
    s.advance(timing.opening_ms // 2)
    assert s.status().door.position is DoorPosition.CLOSED
    assert s.snapshot().mechanism_energy_mj == 500 * (timing.opening_ms // 2)
    s.advance(timing.opening_ms)
    assert s.snapshot().mechanism_energy_mj == 500 * timing.opening_ms
    assert s.snapshot().active is not None and s.snapshot().active.phase is Phase.FAILED
    assert s.feedback()[-1].text == (
        "FAILED C1.1: Drone 01 (1); E_JAMMED: D1 is jammed. "
        "Queue halted; remaining instructions retained."
    )
    assert "2. move m0/R2" in texts(s, "queue show 1")[0]


def test_accounting_is_independent_chunk_invariant_and_capped() -> None:
    a, b = sandbox(), sandbox()
    initial = to_mj(a.status().drone.charge_wh)
    for s in (a, b):
        execute(s, "move 1 R2")
        execute(s, "open D1")
    end = a.timing.opening_ms + 345
    a.advance(end)
    for ms in (100, 241, end - 341):
        b.advance(ms)
    assert a.status() == b.status()
    assert a.snapshot().controller_energy_mj == b.snapshot().controller_energy_mj == end * 20
    assert a.snapshot().mechanism_energy_mj == b.snapshot().mechanism_energy_mj == a.timing.opening_ms * 500
    assert to_mj(a.status().drone.charge_wh) == (
        initial - a.timing.idle_w * a.timing.opening_ms - a.timing.travel_w * 345
    )
    initial_world, _ = load_scenario()
    tiny_world = replace(initial_world, door=a.status().door,
                         drone=replace(a.status().drone, charge_wh=1 / MJ_PER_WH))
    tiny = Session(tiny_world, a.timing)
    execute(tiny, "move 1 R2")
    tiny.advance(100)
    assert tiny.status().drone.charge_wh == 0
    assert tiny.snapshot().active is not None and tiny.snapshot().active.phase is Phase.FAILED
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
    assert s.snapshot().active is not None and s.snapshot().active.step == 1
    assert s.status().door.position is DoorPosition.CLOSED
    s.advance(s.timing.opening_ms)
    assert s.snapshot().active.step == 2 and s.status().door.position is DoorPosition.OPEN
    s.advance(s.timing.waypoint_ms)
    checkpoint = physical(s, Waypoint.BOUNDARY, "D1", Point(8, 3))
    assert not s.report_physical(replace(checkpoint, step=1))
    assert s.report_physical(checkpoint)
    s.advance(s.timing.waypoint_ms)
    assert s.report_physical(physical(s, Waypoint.ARRIVAL, "R2", Point(12, 3)))
    assert s.snapshot().active is None


def test_already_open_steps_do_not_recurse_or_consume_mechanism_energy() -> None:
    world, timing = load_scenario()
    s = Session(replace(world, door=replace(world.door, position=DoorPosition.OPEN)), timing)
    execute(s, "; ".join(["open D1"] * 1200 + ["move 1 R2"]))
    assert s.snapshot().active is not None and s.snapshot().active.step == 1201
    assert s.snapshot().mechanism_energy_mj == 0 and s.snapshot().door_activity is None


@pytest.mark.parametrize(("service", "code"), [
    ("mechanism_powered", "E_POWER"),
    ("controller_powered", "E_CONTROLLER"),
    ("controller_healthy", "E_CONTROLLER"),
    ("controller_data_connected", "E_DATA"),
    ("access_authorized", "E_SECURE"),
])
def test_open_interruption_does_not_credit_outage_or_replace_waiting_route(
    service: str, code: str
) -> None:
    s = sandbox()
    execute(s, "move 1 R2")
    route = s.snapshot().active
    execute(s, "open D1")
    half = s.timing.opening_ms // 2
    s.advance(half)
    door = s.status().door
    s.update_door_services(door.id, replace(door.services, **{service: False}))
    s.advance(s.timing.opening_ms - half - 1)
    s.update_door_services(door.id, door.services)
    s.advance(1)
    assert s.status().door.position is DoorPosition.CLOSED
    assert s.snapshot().mechanism_energy_mj == 500 * half
    assert route is not None and s.snapshot().active == route and route.phase is Phase.WAITING
    failure = s.feedback()[-1]
    assert failure.text.startswith(f"ERROR {code}: ")
    assert failure.stamp_ms == half and failure.command_id == "C2"

    execute(s, "open D1")
    s.advance(s.timing.opening_ms)
    assert s.status().door.position is DoorPosition.OPEN
    assert route is not None and s.snapshot().active is not None
    assert s.snapshot().active.command_id == route.command_id
    assert s.snapshot().active.phase is Phase.RUNNING
    assert s.snapshot().mechanism_energy_mj == 500 * (half + s.timing.opening_ms)


def test_interrupted_queued_open_halts_and_keeps_remaining_queue() -> None:
    s = sandbox()
    execute(s, "open D1; move 1 R2")
    s.advance(100)
    door = s.status().door
    s.update_door_services(door.id, replace(door.services, controller_data_connected=False))
    s.advance(100)
    s.update_door_services(door.id, door.services)
    s.advance(s.timing.opening_ms)
    assert s.status().door.position is DoorPosition.CLOSED
    assert s.snapshot().active is not None and s.snapshot().active.phase is Phase.FAILED
    assert s.feedback()[-1].stamp_ms == 100
    assert "; E_DATA:" in s.feedback()[-1].text
    assert "2. move m0/R2" in texts(s, "queue show 1")[0]
    assert s.snapshot().mechanism_energy_mj == 50_000


@pytest.mark.parametrize("charge_mj", [0, 1, 100, 101])
def test_exhaustion_is_an_exact_timestep_independent_boundary(charge_mj: int) -> None:
    world, timing = load_scenario()
    world = replace(world, door=replace(world.door, position=DoorPosition.OPEN),
                    drone=replace(world.drone, charge_wh=charge_mj / MJ_PER_WH))
    sessions = [Session(world, timing), Session(world, timing), Session(world, timing)]
    for s, parts in zip(sessions, ([10], [1] * 10, [2, 3, 5]), strict=True):
        execute(s, "move 1 R2")
        for part in parts:
            s.advance(part)
        assert s.snapshot().active is not None and s.snapshot().active.phase is Phase.FAILED
        assert s.snapshot().stamp_ms == 10 and to_mj(s.status().drone.charge_wh) == 0
        assert s.feedback()[-1].stamp_ms == charge_mj // timing.travel_w
        assert s.feedback()[-1].command_id == "C1"
        assert "E_POWER" in s.feedback()[-1].text
        assert s.snapshot().controller_energy_mj == 200 and s.snapshot().mechanism_energy_mj == 0
    assert sessions[0].feedback() == sessions[1].feedback() == sessions[2].feedback()
