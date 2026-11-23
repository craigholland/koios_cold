import subprocess
import sys
from unittest.mock import Mock

import pytest

from koios_sim.composition.fixture import load_scenario
from koios_sim.composition.live import launch, serve
from koios_sim.interfaces.bridge import Bridge, MessageError
from koios_sim.interfaces.frames import Decoder, FrameError, encode
from koios_sim.services.traversal.session import Session


def test_frames_reassemble_fragmented_utf8_and_combined_messages() -> None:
    decoder = Decoder()
    first = {"text": "電力"}
    second = {"seq": 2}
    encoded = encode(first)
    split_at = encoded.index("電".encode()) + 1
    assert list(decoder.feed(encoded[:split_at])) == []
    assert list(decoder.feed(encoded[split_at:] + encode(second))) == [first, second]


@pytest.mark.parametrize("data", [b"\xff\n", b"[]\n", b'{"x":NaN}\n', b"x" * 65_537])
def test_malformed_frame_is_rejected(data: bytes) -> None:
    with pytest.raises(FrameError):
        list(Decoder().feed(data))


def test_sequences_and_stale_events_cannot_charge_or_complete_twice() -> None:
    session = Session(*load_scenario())
    bridge = Bridge(session, "test-private")
    bridge.handle({"kind": "hello", "seq": 1, "version": 1, "nonce": "test-private"})
    bridge.handle({"kind": "command", "seq": 2, "text": "move 1 R1"})
    assert session.order is not None
    sequence = 3
    for _ in range(2):
        bridge.handle({"kind": "tick", "seq": sequence, "elapsed_ms": 120})
        sequence += 1
    event = {
        "command_id": session.order.command_id,
        "step": 1,
        "drone_id": session.world.drone.permanent_id,
        "stamp_ms": 240,
        "waypoint": "arrival",
        "target_id": "R1",
        "x_m": 4,
        "y_m": 3,
    }
    reply = bridge.handle({"kind": "physical", "seq": sequence, "event": event})
    assert any("COMPLETED" in row["text"] for row in reply["feedback"])
    before = session.status(), session.stamp_ms, session.feedback()
    with pytest.raises(MessageError, match="sequence"):
        bridge.handle({"kind": "tick", "seq": sequence, "elapsed_ms": 120})
    with pytest.raises(MessageError, match="physical result rejected"):
        bridge.handle({"kind": "physical", "seq": sequence + 1, "event": event})
    with pytest.raises(MessageError, match="unsupported"):
        bridge.handle({"kind": "query", "seq": sequence + 1})
    assert (session.status(), session.stamp_ms, session.feedback()) == before


def test_handshake_and_bad_tick_have_no_effect() -> None:
    session = Session(*load_scenario())
    bridge = Bridge(session, "expected")
    with pytest.raises(MessageError):
        bridge.handle({"kind": "hello", "version": 1, "seq": 1, "nonce": "wrong"})
    bridge.handle({"kind": "hello", "version": 1, "seq": 1, "nonce": "expected"})
    for invalid in (True, 500, -1, "5"):
        with pytest.raises(MessageError):
            bridge.handle({"kind": "tick", "seq": 2, "elapsed_ms": invalid})
    assert session.stamp_ms == 0 and not session.feedback()


def test_actual_launcher_socket_and_child_exit() -> None:
    # A child stand-in exercises the real launcher, socket, both frame directions and normal exit.
    child = """
import json, os, socket

def line(data):
    return json.dumps(data).encode() + b'\\n'

with socket.create_connection(('127.0.0.1', int(os.environ['KOIOS_M0_PORT'])), 4) as client:
    hello = line({'kind':'hello', 'seq':1, 'version':1, 'nonce':os.environ['KOIOS_M0_NONCE']})
    client.sendall(hello[:5])
    client.sendall(hello[5:] + line({'kind':'command', 'seq':2, 'text':'move 1 R2'}))
    with client.makefile('rb') as stream:
        handshake = json.loads(stream.readline())
        reply = json.loads(stream.readline())
        assert handshake['state']['world']['drone']['room_id'] == 'R1'
        assert reply['state']['active']['phase'] == 'waiting'
        assert any('WAITING' in r['text'] for r in reply['feedback'])
"""
    assert launch([sys.executable, "-c", child]) == 0


def test_early_process_exit_is_not_reported_as_ready() -> None:
    assert launch([sys.executable, "-c", "raise SystemExit(7)"]) == 7


def test_startup_timeout_terminates_actual_child(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[subprocess.Popen[bytes]] = []
    start = subprocess.Popen

    def capture(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        proc = start(*args, **kwargs)
        started.append(proc)
        return proc

    monkeypatch.setattr("koios_sim.composition.live.subprocess.Popen", capture)
    assert launch([sys.executable, "-c", "import time; time.sleep(15)"], startup_seconds=0.2) == 1
    assert len(started) == 1 and started[0].poll() is not None


def test_door_feedback_is_keyed_to_confirmed_work_and_external_energy() -> None:
    session = Session(*load_scenario())
    bridge = Bridge(session, "test-device")
    bridge.handle({"kind": "hello", "seq": 1, "version": 1, "nonce": "test-device"})
    bridge.handle({"kind": "pause", "seq": 2, "paused": True})
    reply = bridge.handle({"kind": "command", "seq": 3, "text": "open D1"})
    activity = reply["state"]["door_activity"]
    assert activity["phase"] == "queued" and activity["door_id"] == "D1"
    command_id = activity["command_id"]
    assert reply["feedback"][0]["command_id"] == command_id
    reply = bridge.handle({"kind": "tick", "seq": 4, "elapsed_ms": 250})
    assert reply["state"]["stamp_ms"] == 0
    assert reply["state"]["door_energy_mj"] == {"controller": 0, "mechanism": 0}
    reply = bridge.handle({"kind": "pause", "seq": 5, "paused": False})
    assert reply["state"]["door_activity"]["command_id"] == command_id
    assert reply["state"]["door_activity"]["phase"] == "opening"
    for seq in range(6, 14):
        reply = bridge.handle({"kind": "tick", "seq": seq, "elapsed_ms": 250})
    assert reply["state"]["door_activity"] is None
    assert reply["state"]["world"]["door"]["position"] == "open"
    assert reply["state"]["door_energy_mj"] == {"controller": 40_000, "mechanism": 1_000_000}
    assert reply["feedback"] == [{
        "stamp_ms": 2000, "command_id": command_id, "permanent_target_id": "m0/D1",
        "submitted_slot": None, "origin": "godot", "text": "OPENED: D1.",
    }]


def test_local_receive_abort_settles_without_fabricating_ack() -> None:
    session = Session(*load_scenario())
    peer = Mock()
    child = Mock()
    child.poll.return_value = None
    peer.recv.side_effect = ConnectionAbortedError("local Windows abort")
    assert serve(peer, Bridge(session, "test-abort"), child) == 0
    peer.sendall.assert_not_called()
    assert session.stamp_ms == 0 and session.feedback() == ()
