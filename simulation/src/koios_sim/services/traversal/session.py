"""Own the live M0 world, semantic clock and accepted Operations work."""

from dataclasses import replace

from koios_sim.domain.traversal.manual import validated_room
from koios_sim.domain.traversal.observation import Observation, Sensing, observe
from koios_sim.domain.traversal.operation import (
    CONTROLLER_W,
    DOOR_MECHANISM_W,
    Failure,
    Timing,
    Waypoint,
    can_cross,
    door_failure,
    is_inside,
    spend,
    to_mj,
)
from koios_sim.domain.traversal.world import DoorPosition, DoorServices, Point, World
from koios_sim.services.traversal.commands import (
    assigned_slot,
    bind_order,
    format_query,
    target_id,
)
from koios_sim.services.traversal.contracts import (
    Feedback,
    ManualCycleResult,
    Phase,
    PhysicalEvent,
    Request,
    Verb,
)
from koios_sim.services.traversal.manual_control import ManualControl, RoutePose
from koios_sim.services.traversal.orders import Opening, Order
from koios_sim.services.traversal.snapshots import (
    ActiveOrder,
    DoorActivity,
    DoorReport,
    SessionSnapshot,
    Steering,
)
from koios_sim.services.traversal.status import StatusSnapshot, get_status


class Session:
    """Own one in-memory M0 application from fixture startup through session end.

    Keeps the canonical world, accepted order and independent door work, sole
    semantic clock, control lease, resource counters, feedback and retained
    discovery. Callers inject immutable fixture values and report commands,
    elapsed time, external facts or observed physics. Read values are detached;
    the application neither owns a connection nor interprets wire grammar.
    """
    def __init__(self, world: World, timing: Timing, sensing: Sensing | None = None) -> None:
        self._world = world
        self._timing = timing
        self._sensing = sensing
        self._manual: ManualControl | None = None
        self._discovered_markers: set[str] = set()
        self._stamp_ms = 0
        self._paused = False
        self._context = world.deck_id
        self._controller_energy_mj = 0
        self._mechanism_energy_mj = 0
        self._order: Order | None = None
        self._opening: Opening | None = None
        self._pending_devices: list[tuple[str, str]] = []
        self._next_id = 1
        self._records: list[Feedback] = []
        self._retain_discovery()

    @property
    def timing(self) -> Timing:
        return self._timing

    def status(self) -> StatusSnapshot:
        return get_status(self._world)

    def feedback(self) -> tuple[Feedback, ...]:
        return tuple(self._records)

    def snapshot(self) -> SessionSnapshot:
        """Project committed state, current evidence and retained discovery without writing."""
        order, opening = self._order, self._opening
        door = self._world.door
        active = (ActiveOrder(order.command_id, order.index + 1, order.phase,
                              order.instructions[order.index:], order.crossed,
                              order.segment_ms >= self._timing.waypoint_ms) if order else None)
        door_activity = None
        if opening is not None:
            door_activity = DoorActivity(opening.command_id, door.id, opening.origin, True)
        elif self._pending_devices:
            command_id, origin = self._pending_devices[0]
            door_activity = DoorActivity(command_id, door.id, origin, False)
        facts = door.services
        report = (DoorReport(door.position, self._stamp_ms) if
                  facts.controller_powered and facts.controller_healthy
                  and facts.controller_data_connected else None)
        profile = self._sensing
        steering = (Steering(profile.speed_m_s, profile.turn_deg_s, profile.body_radius_m)
                    if profile is not None else None)
        # Static fixture locations are exposed only for already retained discoveries.
        known_markers = () if profile is None else tuple(sorted(
            (marker for marker in profile.markers if marker.id in self._discovered_markers),
            key=lambda marker: marker.id,
        ))
        return SessionSnapshot(
            self.status(), self._stamp_ms, self._paused, self._context, active,
            None if self._manual is None else self._manual.id,
            self._opening_fraction, door_activity, self._controller_energy_mj,
            self._mechanism_energy_mj, report, self._observation(),
            tuple(sorted(self._discovered_markers)), known_markers, steering,
        )

    def update_door_services(self, door_id: str, facts: DoorServices) -> None:
        """Apply external facts for the identified door, not a world replacement.

        An already active opening rechecks changed service facts at its next
        semantic advance; no time or energy is consumed by this input alone.
        """
        door = self._world.door
        if door_id != door.id:
            raise ValueError("unknown door for the supplied service facts")
        self._world = replace(self._world, door=replace(door, services=facts))
        self._retain_discovery()

    def update_drone_link(self, drone_id: str, *, local_dcl: bool, workstation_route: bool) -> None:
        """Update the identified drone's two link facts without changing pose or orders."""
        drone = self._world.drone
        if drone_id != drone.permanent_id:
            raise ValueError("unknown drone for the supplied link facts")
        self._world = replace(self._world, drone=replace(
            drone, local_dcl_signal=local_dcl, workstation_route_available=workstation_route,
        ))
        self._retain_discovery()

    def _observation(self) -> Observation | None:
        drone, profile = self._world.drone, self._sensing
        if profile is None or not drone.local_dcl_signal or not drone.workstation_route_available:
            return None
        return observe(self._world, profile, self._opening_fraction)

    def _retain_discovery(self) -> None:
        """Accumulate only currently eligible observations at an application boundary."""
        observation = self._observation()
        if observation is not None:
            self._discovered_markers.update(marker.id for marker in observation.visible_markers)

    def _command_id(self) -> str:
        result = f"C{self._next_id}"
        self._next_id += 1
        return result

    def _emit(self, command_id: str, origin: str, text: str, *,
             drone: bool = False, target: str | None = None, slot: int | None = None) -> Feedback:
        if drone:
            target = self._world.drone.permanent_id
            slot = self._world.drone.slot if slot is None else slot
        record = Feedback(self._stamp_ms, command_id, target, slot, origin, text)
        self._records.append(record)
        return record

    def record_command_feedback(self, origin: str, text: str) -> Feedback:
        """Record a parser/help result with the next application ID and current clock."""
        return self._emit(self._command_id(), origin, text)

    def submit(self, requests: tuple[Request, ...], origin: str) -> tuple[Feedback, ...]:
        """Handle nonempty parsed requests atomically and return only new feedback.

        Resolve every target and slot before replacing accepted work. Queue/status
        commands can record feedback but do not mutate the accepted order.
        """
        before = len(self._records)
        command_id = self._command_id()
        if len(requests) > 1 or requests[0].verb is Verb.MOVE:
            bound = bind_order(self._world, self._context, requests)
            if isinstance(bound, Failure):
                self._binding_error(command_id, origin, bound)
            else:
                self._replace_order(Order(command_id, origin, bound))
        else:
            self._submit_single(requests[0], command_id, origin)
        if len(requests) > 1 or requests[0].verb not in (Verb.STATUS, Verb.QUEUE):
            self._retain_discovery()
        return tuple(self._records[before:])

    def _binding_error(self, command_id: str, origin: str, failure: Failure, *,
                       target: str | None = None) -> None:
        self._emit(command_id, origin, f"ERROR {failure.code}: {failure.reason}", target=target)

    def _submit_single(self, req: Request, command_id: str, origin: str) -> None:
        match req.verb:
            case Verb.CONTEXT:
                token = req.args[0]
                if token.casefold() != self._world.deck_id.casefold():
                    self._binding_error(command_id, origin,
                           Failure("E_CONTEXT", f"Unknown deck '{token}'. Context unchanged."))
                else:
                    self._context = self._world.deck_id
                    self._emit(command_id, origin, f"CONTEXT: {self._context}. "
                                 "Camera selection does not change command context.")
            case Verb.OPEN:
                target = target_id(self._world, self._context, "door", req.args[0])
                if isinstance(target, Failure):
                    self._binding_error(command_id, origin, target)
                    return
                door = self._world.door
                # Service and credential validation is repeated when a paused request runs.
                failure = door_failure(door)
                if failure and failure.code != "E_JAMMED" and door.position.value != "open":
                    self._binding_error(command_id, origin, failure, target=f"{self._world.deck_id}/{door.id}")
                    return
                self._start_open(command_id, origin, queued_step=False)
            case Verb.STOP | Verb.QUEUE | Verb.STATUS:
                slot = assigned_slot(self._world, req.args[0])
                if isinstance(slot, Failure):
                    self._binding_error(command_id, origin, slot)
                elif req.verb is Verb.STOP:
                    self._stop(command_id, origin)
                else:
                    self._emit(command_id, origin, format_query(self.snapshot(), req.verb), drone=True)
            case _:
                raise ValueError(f"unsupported application request {req.verb!r}")

    def _order_message(self, order: Order, text: str) -> None:
        step = order.current
        self._emit(order.command_id, order.origin, text, target=step.drone_id,
                  slot=step.submitted_slot)

    @property
    def _short_drone(self) -> str:
        d = self._world.drone
        return f"{d.display_name} ({d.slot})"

    def set_paused(self, paused: bool) -> None:
        """Revoke direct control on pause; on resume, admit pending door requests in order."""
        self._paused = paused
        if paused:
            self._manual = None
        else:
            pending, self._pending_devices = self._pending_devices, []
            for command_id, origin in pending:
                self._start_open(command_id, origin, queued_step=False)
            self._drive_order()
        self._retain_discovery()

    def _replace_order(self, order: Order) -> None:
        """Replace validated work and revoke prior control and order-owned opening only."""
        self._manual = None
        # A cancelled order must not commit a delayed opening or route event.
        if self._opening is not None and self._opening.queued_step:
            self._opening = None
        self._order = order
        if self._paused:
            text = (f"QUEUED {order.command_id}: {self._short_drone}; {len(order.instructions)} "
                    "instruction(s). Waiting for ship time to resume. Previous task and queue replaced.")
        else:
            text = (f"ACCEPTED {order.command_id}: {self._short_drone}; {len(order.instructions)} "
                    "instruction(s). Previous task and queue replaced.")
        self._order_message(order, text)
        self._drive_order()

    def _stop(self, command_id: str, origin: str) -> None:
        """Cancel the lease and route without cancelling independently started door work."""
        self._manual = None
        self._order = None
        if self._opening is not None and self._opening.queued_step:
            self._opening = None
        self._emit(command_id, origin,
                  f"STOPPED: {self._short_drone}; current instruction cancelled and queue cleared.",
                  drone=True)

    @property
    def _opening_fraction(self) -> float:
        door = self._world.door
        if door.position is DoorPosition.OPEN:
            return 1.0
        if self._opening is not None and not door.jammed:
            return 1.0 - self._opening.remaining_ms / self._timing.opening_ms
        return 0.0

    def begin_manual(self, drone_id: str, handoff: RoutePose | None = None) -> bool:
        """Grant the sole lease only after reconciling any currently moving route.

        A moving route requires a compatible pose at its current step and timestamp.
        An accepted handoff commits its physical state before cancelling the route.
        """
        if (self._paused or self._sensing is None or self._manual is not None
                or drone_id != self._world.drone.permanent_id
                or not self._world.drone.workstation_route_available
                or to_mj(self._world.drone.charge_wh) < self._timing.travel_w):
            return False
        moving = self._moving_order()
        if moving is not None or handoff is not None:
            if moving is None or handoff is None:
                return False
            if not self._reconcile_route_pose(moving, handoff):
                self._retain_discovery()
                return False
        self._order = None
        if self._opening is not None and self._opening.queued_step:
            self._opening = None
        identifier = self._command_id()
        self._manual = ManualControl(identifier, drone_id, self._stamp_ms)
        self._emit(identifier, "godot", f"DIRECT CONTROL: {self._short_drone}; prior work cancelled.",
                  drone=True)
        self._retain_discovery()
        return True

    def report_route_pose(self, pose: RoutePose) -> bool:
        """Reconcile sampled autonomous motion without completing an instruction."""
        order = self._moving_order()
        confirmed = not self._paused and order is not None and self._reconcile_route_pose(order, pose)
        self._retain_discovery()
        return confirmed

    def apply_tick(self, elapsed_ms: int, pose: RoutePose | None = None) -> None:
        """Apply a nonnegative millisecond tick, with an optional matching pose sample.

        If the pose cannot reconcile, still advance the valid interval once.
        A pose can fail after advancing the clock when work exhausted its charge;
        in that case the fallback must not advance or charge it again.
        """
        before = self._stamp_ms
        moving = self._moving_order()
        confirmed = (pose is not None and not self._paused and moving is not None
                     and self._reconcile_route_pose(moving, pose))
        if not confirmed and self._stamp_ms == before:
            self._advance(elapsed_ms)
        self._retain_discovery()

    def _reconcile_route_pose(self, order: Order, handoff: RoutePose) -> bool:
        """Validate step/stamp, opening, displacement and heading before committing pose.

        Elapsed time is accounted before applying the pose; exhaustion can still
        invalidate the active order and leave the location unconfirmed.
        """
        sensing = self._sensing
        d = self._world.drone
        if (sensing is None or handoff.command_id != order.command_id
                or handoff.step != order.index + 1 or handoff.stamp_ms != self._stamp_ms
                or not 0 <= handoff.heading < 360 or handoff.elapsed_ms < 0):
            return False
        elapsed = order.travel_ms - order.last_pose_travel_ms + handoff.elapsed_ms
        limit = sensing.speed_m_s * elapsed / 1000 + 0.12
        room = validated_room(self._world, handoff.point, limit,
                              self._opening_fraction, sensing.body_radius_m)
        if room is None or (room != d.room_id and (not order.crossed or room != order.current.target_id)):
            return False
        self._advance(handoff.elapsed_ms)
        if self._moving_order() is not order:
            return False
        self._world = replace(self._world, drone=replace(
            self._world.drone, room_id=room, location=handoff.point, heading_degrees=handoff.heading
        ))
        order.last_pose_travel_ms = order.travel_ms
        return True

    def manual_cycle(self, lease_id: str, drone_id: str, stamp_ms: int | None,
                     elapsed_ms: int | None, point: Point, heading: float, *,
                     release: bool) -> ManualCycleResult:
        """Admit a millisecond lease sample, charge once, then reconcile its pose.

        A stale lease or timestamp never advances time. Missing decoded timing
        is distinguished only when reaching that validation step. An admitted
        interval still advances when the physical report fails to reconcile.
        """
        lease = self._manual
        if lease is None or lease.id != lease_id or lease.drone_id != drone_id or self._paused:
            return ManualCycleResult.UNCONFIRMED
        if stamp_ms is None:
            return ManualCycleResult.INVALID_STAMP
        if stamp_ms != self._stamp_ms:
            return ManualCycleResult.UNCONFIRMED
        if elapsed_ms is None:
            return ManualCycleResult.INVALID_INTERVAL
        self._advance(elapsed_ms)
        confirmed = self._reconcile_manual(lease_id, drone_id, self._stamp_ms, point, heading, release=release)
        self._retain_discovery()
        return ManualCycleResult.CONFIRMED if confirmed else ManualCycleResult.UNCONFIRMED

    def report_manual(self, lease_id: str, drone_id: str, stamp_ms: int, point: Point,
                      heading: float, *, release: bool) -> bool:
        """Reconcile at the current committed stamp without advancing time again.

        The point is in meters and heading in degrees. Release applies only to
        the matching current lease and a valid or unchanged final pose.
        """
        confirmed = self._reconcile_manual(lease_id, drone_id, stamp_ms, point, heading, release=release)
        if confirmed:
            self._retain_discovery()
        return confirmed

    def _reconcile_manual(self, lease_id: str, drone_id: str, stamp_ms: int, point: Point,
                          heading: float, *, release: bool) -> bool:
        lease, sensing = self._manual, self._sensing
        if (self._paused or lease is None or sensing is None or lease.id != lease_id
                or lease.drone_id != drone_id or stamp_ms != self._stamp_ms):
            return False
        if release and point == self._world.drone.location and heading == self._world.drone.heading_degrees:
            self._manual = None
            return True
        state = lease.reconcile(self._world, point, heading, stamp_ms,
                                sensing.speed_m_s, sensing.turn_deg_s,
                                self._opening_fraction, sensing.body_radius_m)
        if state is None:
            return False
        self._world = state
        if release:
            self._manual = None
        return True

    def _start_open(self, command_id: str, origin: str, *, queued_step: bool) -> None:
        door = self._world.door
        if self._paused:
            self._pending_devices.append((command_id, origin))
            self._emit(command_id, origin,
                      f"QUEUED {command_id}: {door.id}; waiting for ship time to resume.",
                      target=f"{self._world.deck_id}/{door.id}")
            return
        if door.position is DoorPosition.OPEN:
            self._emit(command_id, origin, f"UNCHANGED: {door.id} is already open.", target=f"{self._world.deck_id}/{door.id}")
            if queued_step and self._order is not None:
                self._complete_step(self._order)
            return
        failure = door_failure(door)
        # A jammed mechanism is still energized for an attempted motion.
        jammed = failure is not None and failure.code == "E_JAMMED"
        if failure is not None and not jammed:
            self._open_failure(command_id, origin, queued_step, failure.code, failure.reason)
            return
        if self._opening is not None:
            if queued_step:
                return  # Let the in-flight independent request settle; recheck on completion.
            self._open_failure(command_id, origin, False, "E_BUSY", f"{door.id} is busy with opening.")
            return
        self._opening = Opening(command_id, origin, self._timing.opening_ms, queued_step)

    def _open_failure(self, command_id: str, origin: str, queued_step: bool,
                      code: str, reason: str) -> None:
        if queued_step and self._order is not None:
            self._fail_order(self._order, code, reason)
        else:
            self._emit(command_id, origin, f"ERROR {code}: {reason}", target=f"{self._world.deck_id}/{self._world.door.id}")

    def _fail_order(self, order: Order, code: str, reason: str) -> None:
        order.phase = Phase.FAILED
        self._order_message(order, f"FAILED {order.command_id}.{order.index + 1}: "
                            f"{self._short_drone}; {code}: {reason.rstrip('.')}. "
                            "Queue halted; remaining instructions retained.")

    def _drive_order(self) -> None:
        """Start eligible work, pumping immediate already-open steps without recursion."""
        # An already-open door can complete synchronously. Pump the queue iteratively.
        while True:
            before = self._order
            index = before.index if before is not None else None
            self._drive_step()
            if self._order is None or self._order is not before or self._order.index == index:
                return

    def _drive_step(self) -> None:
        order = self._order
        if self._paused or order is None or order.phase is Phase.FAILED:
            return
        step = order.current
        if order.phase is Phase.QUEUED:
            order.phase = Phase.RUNNING
            self._order_message(order, f"RUNNING {order.command_id}.{order.index + 1}: "
                                f"{self._short_drone}; {step.verb} {step.target_id}.")
        if step.verb is Verb.OPEN:
            if self._opening is None:
                self._start_open(order.command_id, order.origin, queued_step=True)
            return
        if step.target_id != self._world.drone.room_id and self._world.door.position is not DoorPosition.OPEN:
            if order.phase is not Phase.WAITING:
                order.phase = Phase.WAITING
                self._order_message(order, f"WAITING: {self._short_drone}; route blocked by "
                                    f"{self._world.door.id}. Open or clear the route to resume.")
        elif order.phase is Phase.WAITING:
            order.phase = Phase.RUNNING
            self._order_message(order, f"RUNNING {order.command_id}.{order.index + 1}: "
                                f"{self._short_drone}; {step.verb} {step.target_id}.")

    def _complete_step(self, order: Order) -> None:
        """Finish the final instruction or reset route counters for the next step."""
        if order.index + 1 == len(order.instructions):
            self._order_message(order,
                                f"COMPLETED {order.command_id}: {self._short_drone}; queue empty.")
            self._order = None
        else:
            order.index += 1
            order.phase = Phase.QUEUED
            order.crossed = False
            order.segment_ms = 0
            order.travel_ms = 0
            order.last_pose_travel_ms = 0

    def advance(self, elapsed_ms: int) -> None:
        """Advance semantic milliseconds without a pose sample; pause freezes the clock."""
        self._advance(elapsed_ms)
        self._retain_discovery()

    def _advance(self, elapsed_ms: int) -> None:
        """Subdivide at door completion and integer-energy exhaustion boundaries."""
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise ValueError("elapsed time must be a nonnegative integer in milliseconds")
        if self._paused:
            return
        while elapsed_ms:
            self._interrupt_opening_if_needed()
            opening = self._opening
            order = self._moving_order()
            interval_ms = min(elapsed_ms, opening.remaining_ms) if opening else elapsed_ms
            exhaustion_ms = None
            if order is not None or self._manual is not None:
                exhaustion_ms = to_mj(self._world.drone.charge_wh) // self._timing.travel_w
                interval_ms = min(interval_ms, exhaustion_ms)

            if interval_ms:
                self._charge(interval_ms, order)
                self._stamp_ms += interval_ms
                elapsed_ms -= interval_ms
                if opening is not None:
                    opening.remaining_ms -= interval_ms

            if order is not None and exhaustion_ms == interval_ms:
                self._fail_order(order, "E_POWER",
                                 f"{self._short_drone} has no usable power for this operation.")
            if self._manual is not None and exhaustion_ms == interval_ms:
                self._manual = None
            if opening is not None and opening.remaining_ms == 0:
                self._finish_open(opening)

    def _interrupt_opening_if_needed(self) -> None:
        opening = self._opening
        if opening is None:
            return
        failure = door_failure(self._world.door)
        # A jammed attempt stays energized through its bounded attempt time.
        if failure is None or failure.code == "E_JAMMED":
            return
        self._opening = None
        self._open_failure(opening.command_id, opening.origin, opening.queued_step,
                           failure.code, failure.reason)
        self._drive_order()

    def _moving_order(self) -> Order | None:
        order = self._order
        if order is not None and order.phase is Phase.RUNNING and order.current.verb is Verb.MOVE:
            return order
        return None

    def _charge(self, elapsed_ms: int, moving: Order | None) -> None:
        """Debit one admitted interval; watts times milliseconds gives millijoules."""
        d, door = self._world.drone, self._world.door
        if door.services.controller_powered:
            self._controller_energy_mj += CONTROLLER_W * elapsed_ms
        if self._opening is not None:
            self._mechanism_energy_mj += DOOR_MECHANISM_W * elapsed_ms
        power = self._timing.travel_w if self._manual is not None else self._timing.idle_w
        if moving is not None:
            power = self._timing.travel_w
            moving.segment_ms += elapsed_ms
            moving.travel_ms += elapsed_ms
        self._world = replace(self._world, drone=replace(d, charge_wh=spend(d.charge_wh, power, elapsed_ms)))

    def _finish_open(self, opening: Opening) -> None:
        self._opening = None
        door = self._world.door
        failure = door_failure(door)
        if failure is not None:
            self._open_failure(opening.command_id, opening.origin, opening.queued_step,
                               failure.code, failure.reason)
            self._drive_order()
            return
        self._world = replace(self._world, door=replace(door, position=DoorPosition.OPEN))
        self._emit(opening.command_id, opening.origin, f"OPENED: {door.id}.", target=f"{self._world.deck_id}/{door.id}")
        if opening.queued_step and self._order is not None:
            self._complete_step(self._order)
        self._drive_order()

    def report_physical(self, event: PhysicalEvent) -> bool:
        """Reconcile a physical checkpoint or arrival for the current route step.

        A checkpoint certifies doorway transit without moving the confirmed room;
        arrival requires the proper room and a prior crossing when applicable.
        Only accepted arrivals progress work. Rejected events mutate nothing.
        """
        order = self._order
        d = self._world.drone
        if (self._paused or order is None or order.phase is not Phase.RUNNING
                or order.current.verb is not Verb.MOVE or event.drone_id != order.current.drone_id
                or event.drone_id != d.permanent_id or event.command_id != order.command_id
                or event.step != order.index + 1 or event.stamp_ms != self._stamp_ms
                or order.segment_ms < self._timing.waypoint_ms or to_mj(d.charge_wh) == 0):
            return False
        heading = d.heading_degrees if event.heading_degrees is None else event.heading_degrees
        if not 0 <= heading < 360:
            return False
        if event.waypoint is Waypoint.BOUNDARY:
            if (order.crossed or order.current.target_id == d.room_id
                    or event.target_id != self._world.door.id
                    or not can_cross(self._world.door, event.point)):
                return False
            self._world = replace(self._world, drone=replace(d, heading_degrees=heading))
            order.crossed = True  # Verified doorway checkpoint, not a new reported room.
            order.segment_ms = 0
            self._retain_discovery()
            return True
        if event.waypoint is not Waypoint.ARRIVAL or event.target_id != order.current.target_id:
            return False
        room = next(r for r in self._world.rooms if r.id == event.target_id)
        if not is_inside(room, event.point) or (room.id != d.room_id and not order.crossed):
            return False
        self._world = replace(self._world, drone=replace(
            d, room_id=room.id, location=event.point, heading_degrees=heading,
        ))
        self._order_message(order, f"ARRIVED: {self._short_drone}; room={room.id}.")
        self._complete_step(order)
        self._drive_order()
        self._retain_discovery()
        return True
