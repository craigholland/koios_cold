"""Application query over the authoritative traversal world."""

from dataclasses import dataclass

from koios_sim.domain.traversal.world import Door, Drone, Room, World


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    deck_id: str
    rooms: tuple[Room, Room]
    door: Door
    drone: Drone


def get_status(world: World) -> StatusSnapshot:
    """Project a read-only value from the supplied live world, not a fixture reread."""
    return StatusSnapshot(world.deck_id, world.rooms, world.door, world.drone)
