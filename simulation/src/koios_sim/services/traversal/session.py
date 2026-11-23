"""Own the live M0 world, semantic clock and accepted Operations work."""

from dataclasses import replace

from koios_sim.domain.traversal.manual import validated_room
from koios_sim.domain.traversal.observation import Sensing
from koios_sim.domain.traversal.operation import (
    CONTROLLER_W,
    DOOR_MECHANISM_W,
    Timing,
    Waypoint,
    can_cross,
    door_failure,
    is_inside,
    spend,
    to_mj,
)
from koios_sim.domain.traversal.world import DoorPosition, Point, World
from koios_sim.services.traversal.contracts import (
    Feedback,
    Phase,
    PhysicalEvent,
    Verb,
)
from koios_sim.services.traversal.manual_control import ManualControl, RoutePose
from koios_sim.services.traversal.orders import Opening, Order
from koios_sim.services.traversal.status import StatusSnapshot, get_status


class Session:
    def __init__(self, world: World, timing: Timing, sensing: Sensing | None = None) -> None:
        self.world = world
        self.timing = timing
        self.sensing = sensing
        self.manual: ManualControl | None = None
        self.discovered_markers: set[str] = set()
        self.stamp_ms = 0
        self.paused = False
        self.context = world.deck_id
        self.controller_energy_mj = 0
        self.mechanism_energy_mj = 0
        self.order: Order | None = None
        self.opening: Opening | None = None
        self.pending_devices: list[tuple[str, str]] = []
        self._next_id = 1
        self._records: list[Feedback] = []

    def status(self) -> StatusSnapshot:
        return get_status(self.world)

    def feedback(self) -> tuple[Feedback, ...]:
        return tuple(self._records)

    def command_id(self) -> str:
        result = f"C{self._next_id}"
        self._next_id += 1
        return result

    def emit(self, command_id: str, origin: str, text: str, *,
             drone: bool = False, target: str | None = None, slot: int | None = None) -> Feedback:
        if drone:
            target = self.world.drone.permanent_id
            slot = self.world.drone.slot if slot is None else slot
        record = Feedback(self.stamp_ms, command_id, target, slot, origin, text)
        self._records.append(record)
        return record

    def _order_message(self, order: Order, text: str) -> None:
        step = order.current
        self.emit(order.command_id, order.origin, text, target=step.drone_id,
                  slot=step.submitted_slot)

    @property
    def short_drone(self) -> str:
        d = self.world.drone
        return f"{d.display_name} ({d.slot})"

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        if paused:
            self.manual = None
        else:
            pending, self.pending_devices = self.pending_devices, []
            for command_id, origin in pending:
                self.start_open(command_id, origin, queued_step=False)
            self.drive_order()

    def replace_order(self, order: Order) -> None:
        self.manual = None
        # A cancelled order must not commit a delayed opening or route event.
        if self.opening is not None and self.opening.queued_step:
            self.opening = None
        self.order = order
        if self.paused:
            text = (f"QUEUED {order.command_id}: {self.short_drone}; {len(order.instructions)} "
                    "instruction(s). Waiting for ship time to resume. Previous task and queue replaced.")
        else:
            text = (f"ACCEPTED {order.command_id}: {self.short_drone}; {len(order.instructions)} "
                    "instruction(s). Previous task and queue replaced.")
        self._order_message(order, text)
        self.drive_order()

    def stop(self, command_id: str, origin: str) -> None:
        self.manual = None
        self.order = None
        if self.opening is not None and self.opening.queued_step:
            self.opening = None
        self.emit(command_id, origin,
                  f"STOPPED: {self.short_drone}; current instruction cancelled and queue cleared.",
                  drone=True)

    @property
    def opening_fraction(self) -> float:
        door = self.world.door
        if door.position is DoorPosition.OPEN:
            return 1.0
        if self.opening is not None and not door.jammed:
            return 1.0 - self.opening.remaining_ms / self.timing.opening_ms
        return 0.0

    def begin_manual(self, drone_id: str, handoff: RoutePose | None = None) -> bool:
        if (self.paused or self.sensing is None or self.manual is not None
                or drone_id != self.world.drone.permanent_id
                or not self.world.drone.workstation_route_available
                or to_mj(self.world.drone.charge_wh) < self.timing.travel_w):
            return False
        moving = self._moving_order()
        if moving is not None or handoff is not None:
            if moving is None or handoff is None or not self._reconcile_route_pose(moving, handoff):
                return False
        self.order = None
        if self.opening is not None and self.opening.queued_step:
            self.opening = None
        identifier = self.command_id()
        self.manual = ManualControl(identifier, drone_id, self.stamp_ms)
        self.emit(identifier, "godot", f"DIRECT CONTROL: {self.short_drone}; prior work cancelled.",
                  drone=True)
        return True

    def report_route_pose(self, pose: RoutePose) -> bool:
        """Reconcile sampled autonomous motion without completing an instruction."""
        order = self._moving_order()
        return not self.paused and order is not None and self._reconcile_route_pose(order, pose)

    def _reconcile_route_pose(self, order: Order, handoff: RoutePose) -> bool:
        sensing = self.sensing
        d = self.world.drone
        if (sensing is None or handoff.command_id != order.command_id
                or handoff.step != order.index + 1 or handoff.stamp_ms != self.stamp_ms
                or not 0 <= handoff.heading < 360 or handoff.elapsed_ms < 0):
            return False
        elapsed = order.travel_ms - order.last_pose_travel_ms + handoff.elapsed_ms
        limit = sensing.speed_m_s * elapsed / 1000 + 0.12
        room = validated_room(self.world, handoff.point, limit,
                              self.opening_fraction, sensing.body_radius_m)
        if room is None or (room != d.room_id and (not order.crossed or room != order.current.target_id)):
            return False
        self.advance(handoff.elapsed_ms)
        if self._moving_order() is not order:
            return False
        self.world = replace(self.world, drone=replace(
            self.world.drone, room_id=room, location=handoff.point, heading_degrees=handoff.heading
        ))
        order.last_pose_travel_ms = order.travel_ms
        return True

    def report_manual(self, lease_id: str, drone_id: str, stamp_ms: int, point: Point,
                      heading: float, *, release: bool) -> bool:
        lease, sensing = self.manual, self.sensing
        if (self.paused or lease is None or sensing is None or lease.id != lease_id
                or lease.drone_id != drone_id or stamp_ms != self.stamp_ms):
            return False
        if release and point == self.world.drone.location and heading == self.world.drone.heading_degrees:
            self.manual = None
            return True
        state = lease.reconcile(self.world, point, heading, stamp_ms,
                                sensing.speed_m_s, sensing.turn_deg_s,
                                self.opening_fraction, sensing.body_radius_m)
        if state is None:
            return False
        self.world = state
        if release:
            self.manual = None
        return True

    def start_open(self, command_id: str, origin: str, *, queued_step: bool) -> None:
        door = self.world.door
        if self.paused:
            self.pending_devices.append((command_id, origin))
            self.emit(command_id, origin,
                      f"QUEUED {command_id}: {door.id}; waiting for ship time to resume.",
                      target=f"{self.world.deck_id}/{door.id}")
            return
        if door.position is DoorPosition.OPEN:
            self.emit(command_id, origin, f"UNCHANGED: {door.id} is already open.", target=f"{self.world.deck_id}/{door.id}")
            if queued_step and self.order is not None:
                self._complete_step(self.order)
            return
        failure = door_failure(door)
        # A jammed mechanism is still energized for an attempted motion.
        jammed = failure is not None and failure.code == "E_JAMMED"
        if failure is not None and not jammed:
            self._open_failure(command_id, origin, queued_step, failure.code, failure.reason)
            return
        if self.opening is not None:
            if queued_step:
                return  # Let the in-flight independent request settle; recheck on completion.
            self._open_failure(command_id, origin, False, "E_BUSY", f"{door.id} is busy with opening.")
            return
        self.opening = Opening(command_id, origin, self.timing.opening_ms, queued_step)

    def _open_failure(self, command_id: str, origin: str, queued_step: bool,
                      code: str, reason: str) -> None:
        if queued_step and self.order is not None:
            self._fail_order(self.order, code, reason)
        else:
            self.emit(command_id, origin, f"ERROR {code}: {reason}", target=f"{self.world.deck_id}/{self.world.door.id}")

    def _fail_order(self, order: Order, code: str, reason: str) -> None:
        order.phase = Phase.FAILED
        self._order_message(order, f"FAILED {order.command_id}.{order.index + 1}: "
                            f"{self.short_drone}; {code}: {reason.rstrip('.')}. "
                            "Queue halted; remaining instructions retained.")

    def drive_order(self) -> None:
        # An already-open door can complete synchronously. Pump the queue iteratively.
        while True:
            before = self.order
            index = before.index if before is not None else None
            self._drive_step()
            if self.order is None or self.order is not before or self.order.index == index:
                return

    def _drive_step(self) -> None:
        order = self.order
        if self.paused or order is None or order.phase is Phase.FAILED:
            return
        step = order.current
        if order.phase is Phase.QUEUED:
            order.phase = Phase.RUNNING
            self._order_message(order, f"RUNNING {order.command_id}.{order.index + 1}: "
                                f"{self.short_drone}; {step.verb} {step.target_id}.")
        if step.verb is Verb.OPEN:
            if self.opening is None:
                self.start_open(order.command_id, order.origin, queued_step=True)
            return
        if step.target_id != self.world.drone.room_id and self.world.door.position is not DoorPosition.OPEN:
            if order.phase is not Phase.WAITING:
                order.phase = Phase.WAITING
                self._order_message(order, f"WAITING: {self.short_drone}; route blocked by "
                                    f"{self.world.door.id}. Open or clear the route to resume.")
        elif order.phase is Phase.WAITING:
            order.phase = Phase.RUNNING
            self._order_message(order, f"RUNNING {order.command_id}.{order.index + 1}: "
                                f"{self.short_drone}; {step.verb} {step.target_id}.")

    def _complete_step(self, order: Order) -> None:
        if order.index + 1 == len(order.instructions):
            self._order_message(order,
                                f"COMPLETED {order.command_id}: {self.short_drone}; queue empty.")
            self.order = None
        else:
            order.index += 1
            order.phase = Phase.QUEUED
            order.crossed = False
            order.segment_ms = 0
            order.travel_ms = 0
            order.last_pose_travel_ms = 0

    def advance(self, elapsed_ms: int) -> None:
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise ValueError("elapsed time must be a nonnegative integer in milliseconds")
        if self.paused:
            return
        while elapsed_ms:
            self._interrupt_opening_if_needed()
            opening = self.opening
            order = self._moving_order()
            interval_ms = min(elapsed_ms, opening.remaining_ms) if opening else elapsed_ms
            exhaustion_ms = None
            if order is not None or self.manual is not None:
                exhaustion_ms = to_mj(self.world.drone.charge_wh) // self.timing.travel_w
                interval_ms = min(interval_ms, exhaustion_ms)

            if interval_ms:
                self._charge(interval_ms, order)
                self.stamp_ms += interval_ms
                elapsed_ms -= interval_ms
                if opening is not None:
                    opening.remaining_ms -= interval_ms

            if order is not None and exhaustion_ms == interval_ms:
                self._fail_order(order, "E_POWER",
                                 f"{self.short_drone} has no usable power for this operation.")
            if self.manual is not None and exhaustion_ms == interval_ms:
                self.manual = None
            if opening is not None and opening.remaining_ms == 0:
                self._finish_open(opening)

    def _interrupt_opening_if_needed(self) -> None:
        opening = self.opening
        if opening is None:
            return
        failure = door_failure(self.world.door)
        # A jammed attempt stays energized through its bounded attempt time.
        if failure is None or failure.code == "E_JAMMED":
            return
        self.opening = None
        self._open_failure(opening.command_id, opening.origin, opening.queued_step,
                           failure.code, failure.reason)
        self.drive_order()

    def _moving_order(self) -> Order | None:
        order = self.order
        if order is not None and order.phase is Phase.RUNNING and order.current.verb is Verb.MOVE:
            return order
        return None

    def _charge(self, elapsed_ms: int, moving: Order | None) -> None:
        d, door = self.world.drone, self.world.door
        if door.services.controller_powered:
            self.controller_energy_mj += CONTROLLER_W * elapsed_ms
        if self.opening is not None:
            self.mechanism_energy_mj += DOOR_MECHANISM_W * elapsed_ms
        power = self.timing.travel_w if self.manual is not None else self.timing.idle_w
        if moving is not None:
            power = self.timing.travel_w
            moving.segment_ms += elapsed_ms
            moving.travel_ms += elapsed_ms
        self.world = replace(self.world, drone=replace(d, charge_wh=spend(d.charge_wh, power, elapsed_ms)))

    def _finish_open(self, opening: Opening) -> None:
        self.opening = None
        door = self.world.door
        failure = door_failure(door)
        if failure is not None:
            self._open_failure(opening.command_id, opening.origin, opening.queued_step,
                               failure.code, failure.reason)
            self.drive_order()
            return
        self.world = replace(self.world, door=replace(door, position=DoorPosition.OPEN))
        self.emit(opening.command_id, opening.origin, f"OPENED: {door.id}.", target=f"{self.world.deck_id}/{door.id}")
        if opening.queued_step and self.order is not None:
            self._complete_step(self.order)
        self.drive_order()

    def report_physical(self, event: PhysicalEvent) -> bool:
        """Accept one timely, identity-bound report from the physics boundary."""
        order = self.order
        d = self.world.drone
        if (self.paused or order is None or order.phase is not Phase.RUNNING
                or order.current.verb is not Verb.MOVE or event.drone_id != order.current.drone_id
                or event.drone_id != d.permanent_id or event.command_id != order.command_id
                or event.step != order.index + 1 or event.stamp_ms != self.stamp_ms
                or order.segment_ms < self.timing.waypoint_ms or to_mj(d.charge_wh) == 0):
            return False
        heading = d.heading_degrees if event.heading_degrees is None else event.heading_degrees
        if not 0 <= heading < 360:
            return False
        if event.waypoint is Waypoint.BOUNDARY:
            if (order.crossed or order.current.target_id == d.room_id
                    or event.target_id != self.world.door.id
                    or not can_cross(self.world.door, event.point)):
                return False
            self.world = replace(self.world, drone=replace(d, heading_degrees=heading))
            order.crossed = True  # Verified doorway checkpoint, not a new reported room.
            order.segment_ms = 0
            return True
        if event.waypoint is not Waypoint.ARRIVAL or event.target_id != order.current.target_id:
            return False
        room = next(r for r in self.world.rooms if r.id == event.target_id)
        if not is_inside(room, event.point) or (room.id != d.room_id and not order.crossed):
            return False
        self.world = replace(self.world, drone=replace(
            d, room_id=room.id, location=event.point, heading_degrees=heading,
        ))
        self._order_message(order, f"ARRIVED: {self.short_drone}; room={room.id}.")
        self._complete_step(order)
        self.drive_order()
        return True
