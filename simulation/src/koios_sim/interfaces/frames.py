"""Bounded newline-delimited UTF-8 JSON framing for the local M0 adapter."""

import json
from collections.abc import Iterable
from typing import cast

MAX_FRAME_BYTES = 65_536


class FrameError(ValueError):
    """Invalid or unreasonably large wire frame."""


class Decoder:
    def __init__(self) -> None:
        self._pending = bytearray()

    def feed(self, data: bytes) -> Iterable[dict[str, object]]:
        self._pending.extend(data)
        while (end := self._pending.find(b"\n")) >= 0:
            if not 0 < end <= MAX_FRAME_BYTES:
                raise FrameError("invalid frame size")
            frame = bytes(self._pending[:end])
            del self._pending[:end + 1]
            try:
                value = json.loads(frame.decode("utf-8"), parse_constant=_invalid_constant)
            except (UnicodeError, ValueError) as exc:
                raise FrameError("invalid JSON frame") from exc
            if not isinstance(value, dict):
                raise FrameError("expected a JSON object")
            yield cast(dict[str, object], value)
        if len(self._pending) > MAX_FRAME_BYTES:
            raise FrameError("oversized incomplete frame")


def _invalid_constant(token: str) -> None:
    raise FrameError(f"non-finite constant: {token}")


def encode(message: dict[str, object]) -> bytes:
    frame = json.dumps(message, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    data = frame.encode("utf-8")
    if not 0 < len(data) <= MAX_FRAME_BYTES:
        raise FrameError("invalid outbound frame size")
    return data + b"\n"
