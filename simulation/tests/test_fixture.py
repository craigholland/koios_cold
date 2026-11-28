import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from importlib.resources import files
from typing import Any

import pytest

from koios_sim.composition.fixture import FixtureError, decode_fixture, load_m0
from koios_sim.domain.traversal.world import DoorPosition
from koios_sim.services.traversal.status import get_status


def _definition() -> dict[str, Any]:
    return json.loads(files("koios_sim.composition").joinpath("fixtures", "m0.json").read_text(
        encoding="utf-8"
    ))


def test_fixture_relationships_and_status_from_supplied_world() -> None:
    world = load_m0()
    other = load_m0()
    assert world is not other and world.drone is not other.drone
    assert {room.id for room in world.rooms} == set(world.door.rooms)
    assert world.drone.room_id == world.rooms[0].id
    assert world.drone.permanent_id != world.drone.display_name
    assert world.drone.slot == 1
    assert world.drone.local_dcl_signal and world.drone.workstation_route_available
    assert world.door.position is DoorPosition.CLOSED and not world.door.jammed

    changed = replace(world, door=replace(world.door, services=replace(
        world.door.services, controller_data_connected=False
    )), drone=replace(world.drone, charge_wh=world.drone.charge_wh - 1))
    snapshot = get_status(changed)
    assert snapshot.drone.charge_wh == get_status(world).drone.charge_wh - 1
    assert not snapshot.door.services.controller_data_connected
    assert snapshot.door.services.mechanism_powered
    assert get_status(world).door.services.controller_data_connected
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot.drone, "charge_wh", 0)


@pytest.mark.parametrize(("path", "value", "message"), [
    (("door", "rooms"), ["R1", "R9"], "endpoints"),
    (("door", "rooms"), ["R1", "R1"], "distinct rooms"),
    (("door", "id"), "R1", "door ID"),
    (("door", "gap_start"), [8, 7], "ordered axis-aligned"),
    (("door", "gap_end"), [9, 2], "shared wall"),
    (("door", "services", "controller_powered"), "true", "must be a boolean"),
    (("drone", "slot"), True, "must be an integer"),
    (("drone", "room_id"), "R9", "unknown room"),
    (("drone", "location"), [20, 3], "inside its referenced room"),
    (("drone", "capacity_wh"), 0, "positive capacity"),
    (("drone", "charge_wh"), -1, "positive capacity"),
    (("drone", "capacity_wh"), 1, "positive capacity"),
    (("drone", "charge_wh"), float("nan"), "finite number"),
    (("drone", "condition_pct"), 101, "condition"),
    (("drone", "heading_degrees"), 360, "heading"),
])
def test_invalid_fixture(path: tuple[str, ...], value: object, message: str) -> None:
    definition = _definition()
    current = definition
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    with pytest.raises(FixtureError, match=message):
        decode_fixture(json.dumps(definition))


def test_duplicate_room() -> None:
    definition = _definition()
    definition["rooms"][1]["id"] = definition["rooms"][0]["id"]
    with pytest.raises(FixtureError, match="duplicate room ID"):
        decode_fixture(json.dumps(definition))


@pytest.mark.parametrize("text", ["{broken", "[]", '{"missing":1}', '{"deck_id":1,"deck_id":2}'])
def test_malformed_document(text: str) -> None:
    with pytest.raises(FixtureError):
        decode_fixture(text)


def test_installed_module_cli_matches_public_state(tmp_path: object) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "koios_sim.composition.main"],
        capture_output=True, check=True, text=True, cwd=str(tmp_path),
    )
    payload = json.loads(result.stdout)
    snapshot = get_status(load_m0())
    assert payload["drone"]["permanent_id"] == snapshot.drone.permanent_id
    assert payload["drone"]["room_id"] == snapshot.drone.room_id
    assert payload["door"]["position"] == snapshot.door.position
    assert set(payload["door"]["rooms"]) == {room["id"] for room in payload["rooms"]}


def test_domain_import_does_not_load_application_or_adapters() -> None:
    subprocess.run(
        [sys.executable, "-c",
         "import sys; import koios_sim.domain.traversal.world; "
         "assert not any(x.startswith(('koios_sim.composition', 'koios_sim.services', "
         "'koios_sim.interfaces')) for x in sys.modules)"],
        check=True,
    )
