"""Structured application requests, observations and physical events."""

from dataclasses import dataclass
from enum import StrEnum

from koios_sim.domain.traversal.operation import Waypoint
from koios_sim.domain.traversal.world import Point


class Verb(StrEnum):
    MOVE = "move"
    OPEN = "open"
    STOP = "stop"
    STATUS = "status"
    QUEUE = "queue"
    CONTEXT = "context"
    HELP = "help"


@dataclass(frozen=True, slots=True)
class Request:
    verb: Verb
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Instruction:
    verb: Verb
    target_id: str
    deck_id: str
    drone_id: str | None
    submitted_slot: int | None

    @property
    def address(self) -> str:
        return f"{self.deck_id}/{self.target_id}"


@dataclass(frozen=True, slots=True)
class Feedback:
    stamp_ms: int
    command_id: str
    permanent_target_id: str | None
    submitted_slot: int | None
    origin: str
    text: str


@dataclass(frozen=True, slots=True)
class PhysicalEvent:
    command_id: str
    step: int
    drone_id: str
    stamp_ms: int
    waypoint: Waypoint
    target_id: str
    point: Point
    heading_degrees: float | None = None


class Phase(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    FAILED = "failed"
