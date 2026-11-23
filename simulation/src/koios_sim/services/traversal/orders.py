"""Volatile, identified work accepted by the M0 application service."""

from dataclasses import dataclass

from koios_sim.services.traversal.contracts import Instruction, Phase


@dataclass(slots=True)
class Order:
    command_id: str
    origin: str
    instructions: tuple[Instruction, ...]
    index: int = 0
    phase: Phase = Phase.QUEUED
    segment_ms: int = 0
    crossed: bool = False

    @property
    def current(self) -> Instruction:
        return self.instructions[self.index]


@dataclass(slots=True)
class Opening:
    command_id: str
    origin: str
    remaining_ms: int
    queued_step: bool
