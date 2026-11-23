"""Immutable application projections; no transport names or mutable work."""

from dataclasses import dataclass

from koios_sim.domain.traversal.observation import Observation
from koios_sim.domain.traversal.world import DoorPosition
from koios_sim.services.traversal.contracts import Instruction, Phase
from koios_sim.services.traversal.status import StatusSnapshot


@dataclass(frozen=True, slots=True)
class ActiveOrder:
    """Stable read of one addressed step and remaining immutable instructions."""
    command_id: str
    step: int
    phase: Phase
    remaining: tuple[Instruction, ...]
    crossed: bool
    waypoint_ready: bool

    @property
    def current(self) -> Instruction:
        return self.remaining[0]


@dataclass(frozen=True, slots=True)
class DoorActivity:
    command_id: str
    door_id: str
    origin: str
    opening: bool


@dataclass(frozen=True, slots=True)
class DoorReport:
    position: DoorPosition
    stamp_ms: int


@dataclass(frozen=True, slots=True)
class Steering:
    speed_m_s: float
    turn_deg_s: float
    body_radius_m: float


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    """Point-in-time application values, safe to retain after later operations.

    Current observation can disappear if its route is lost; discovery records
    what was previously retained. Neither reading nor serializing this value
    can advance work or add discovery.
    """
    world: StatusSnapshot
    stamp_ms: int
    paused: bool
    context: str
    active: ActiveOrder | None
    manual_lease: str | None
    opening_fraction: float
    door_activity: DoorActivity | None
    controller_energy_mj: int
    mechanism_energy_mj: int
    door_report: DoorReport | None
    observation: Observation | None
    discovered_markers: tuple[str, ...]
    steering: Steering | None
