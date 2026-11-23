"""One accepted, identified direct-control lease for the M0 assigned drone."""

from dataclasses import dataclass, replace

from koios_sim.domain.traversal.manual import validated_room
from koios_sim.domain.traversal.world import Point, World


@dataclass(frozen=True, slots=True)
class RoutePose:
    """Physical pose for a specific in-flight step, with stamp and interval in ms."""
    command_id: str
    step: int
    stamp_ms: int
    elapsed_ms: int
    point: Point
    heading: float


@dataclass(slots=True)
class ManualControl:
    """Internally held direct-control lease and last accepted report timestamp.

    Session grants/revokes the lease. This value reconciles later physical
    reports against the already committed world, bounds and elapsed travel.
    """
    id: str
    drone_id: str
    last_report_ms: int

    def reconcile(self, world: World, point: Point, heading: float, stamp_ms: int,
                  speed: float, turn: float, aperture: float, radius: float) -> World | None:
        """Check pose plausibility in meters/degrees and advance the lease on success.

        Rejected samples leave both the lease timestamp and world unchanged.
        """
        if stamp_ms <= self.last_report_ms or not 0 <= heading < 360:
            return None
        elapsed = (stamp_ms - self.last_report_ms) / 1000
        delta = (heading - world.drone.heading_degrees + 180) % 360 - 180
        if abs(delta) > turn * elapsed + 2.0:
            return None
        room_id = validated_room(world, point, speed * elapsed + 0.12, aperture, radius)
        if room_id is None:
            return None
        self.last_report_ms = stamp_ms
        return replace(world, drone=replace(world.drone, room_id=room_id, location=point,
                                            heading_degrees=heading))
