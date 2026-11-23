"""Own the bounded, single-client Windows development process lifecycle."""

import argparse
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path
from time import monotonic

from koios_sim.composition.fixture import load_scenario
from koios_sim.interfaces.bridge import Bridge, MessageError
from koios_sim.interfaces.frames import Decoder, FrameError, encode
from koios_sim.services.traversal.session import Session


def serve(client: socket.socket, bridge: Bridge, child: subprocess.Popen[bytes]) -> int:
    client.settimeout(0.25)
    client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    decoder = Decoder()
    while child.poll() is None:
        try:
            data = client.recv(16_384)
        except TimeoutError:
            continue
        if not data:
            return 0
        try:
            for request in decoder.feed(data):
                client.sendall(encode(bridge.handle(request)))
        except (FrameError, MessageError) as exc:
            client.sendall(encode({"kind": "error", "message": str(exc)}))
            return 1
    return child.returncode or 0


def launch(argv: list[str], *, startup_seconds: float = 12.0) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(0.2)
        nonce = secrets.token_hex(16)
        env = {**os.environ, "KOIOS_M0_PORT": str(listener.getsockname()[1]), "KOIOS_M0_NONCE": nonce}
        deadline = monotonic() + startup_seconds
        child = subprocess.Popen(argv, env=env)
        try:
            while child.poll() is None and monotonic() < deadline:
                try:
                    client, _ = listener.accept()
                except TimeoutError:
                    continue
                # One local frontend only; do not accept reconnects or replay uncertain requests.
                listener.close()
                with client:
                    result = serve(client, Bridge(Session(*load_scenario()), nonce), child)
                if result != 0:
                    # Let the frontend show the failure until the developer closes it.
                    child.wait()
                    return result
                try:
                    return child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    print("M0 backend disconnected; close the Godot window to end the launcher.",
                          file=sys.stderr)
                    return child.wait()
            if child.poll() is not None:
                print("M0 Godot exited before connecting.", file=sys.stderr)
                return child.returncode or 1
            print("M0 Godot did not connect before the startup deadline.", file=sys.stderr)
            return 1
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the local Koios M0 Godot sandbox.")
    parser.add_argument("--godot", required=True, help="Path to Godot's Windows executable")
    parser.add_argument("--project", default="frontend", help="Godot project directory")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--log-file", type=Path, help="Optional Godot log path")
    parser.add_argument("--smoke", action="store_true", help="Run and quit a real traversal demo")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    godot = Path(args.godot).resolve()
    if not (project / "project.godot").is_file() or not godot.is_file():
        parser.error("Godot executable or project.godot not found")
    argv = [str(godot), "--path", str(project)]
    if args.log_file is not None:
        argv.extend(["--log-file", str(args.log_file.resolve())])
    if args.headless:
        argv.append("--headless")
    if args.smoke:
        argv.extend(["--", "--smoke"])
    try:
        return launch(argv)
    except (OSError, KeyboardInterrupt) as exc:
        print(f"M0 launch interrupted: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
