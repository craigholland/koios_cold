"""Bind parsed requests to the single known M0 world before changing work."""

from koios_sim.domain.traversal.operation import Failure, door_failure
from koios_sim.services.traversal.contracts import Feedback, Instruction, Request, Verb
from koios_sim.services.traversal.orders import Order
from koios_sim.services.traversal.session import Session


def submit(session: Session, requests: tuple[Request, ...], origin: str) -> tuple[Feedback, ...]:
    before = len(session.feedback())
    command_id = session.command_id()
    if len(requests) > 1 or requests[0].verb is Verb.MOVE:
        _submit_order(session, requests, command_id, origin)
    else:
        _single(session, requests[0], command_id, origin)
    return session.feedback()[before:]


def _error(session: Session, command_id: str, origin: str, failure: Failure, *,
           target: str | None = None, slot: int | None = None) -> None:
    session.emit(command_id, origin, f"ERROR {failure.code}: {failure.reason}", target=target, slot=slot)


def _target(session: Session, kind: str, token: str) -> str | Failure:
    prefix, slash, local = token.partition("/")
    deck, name = (prefix, local) if slash else (session.context, prefix)
    candidates = (
        (session.world.door.id,) if kind == "door" else tuple(r.id for r in session.world.rooms)
    )
    if deck.casefold() == session.world.deck_id.casefold():
        for candidate in candidates:
            if name.casefold() == candidate.casefold():
                return candidate
    return Failure("E_UNKNOWN_ID", f"Unknown {kind} '{token}' in context '{session.context}'.")


def _slot(session: Session, value: str) -> int | Failure:
    assigned = session.world.drone.slot
    if value == "all" or value == str(assigned):
        return assigned
    return Failure("E_SLOT", f"Slot {value} is empty or outside the effective team cap.")


def _submit_order(session: Session, requests: tuple[Request, ...],
                  command_id: str, origin: str) -> None:
    slots = {request.args[0] for request in requests if request.verb is Verb.MOVE}
    if len(slots) != 1 or any(r.verb not in (Verb.MOVE, Verb.OPEN) for r in requests):
        _error(session, command_id, origin, Failure(
            "E_SEQUENCE",
            "A semicolon sequence must target one assigned drone and contain only drone "
            "actions and supported door requests.",
        ))
        return
    targets: list[str] = []
    for req in requests:
        target = _target(session, "room", req.args[1]) if req.verb is Verb.MOVE else _target(
            session, "door", req.args[0]
        )
        if isinstance(target, Failure):
            _error(session, command_id, origin, target)
            return
        targets.append(target)
    slot = _slot(session, slots.pop())
    if isinstance(slot, Failure):
        _error(session, command_id, origin, slot)
        return
    instructions = tuple(Instruction(
        req.verb, target, session.world.deck_id, session.world.drone.permanent_id, slot
    ) for req, target in zip(requests, targets, strict=True))
    session.replace_order(Order(command_id, origin, instructions))


def _single(session: Session, req: Request, command_id: str, origin: str) -> None:
    match req.verb:
        case Verb.CONTEXT:
            token = req.args[0]
            if token.casefold() != session.world.deck_id.casefold():
                _error(session, command_id, origin,
                       Failure("E_CONTEXT", f"Unknown deck '{token}'. Context unchanged."))
            else:
                session.context = session.world.deck_id
                session.emit(command_id, origin, f"CONTEXT: {session.context}. "
                             "Camera selection does not change command context.")
        case Verb.OPEN:
            target = _target(session, "door", req.args[0])
            if isinstance(target, Failure):
                _error(session, command_id, origin, target)
                return
            door = session.world.door
            # Service and credential validation is repeated when a paused request runs.
            failure = door_failure(door)
            if failure and failure.code != "E_JAMMED" and door.position.value != "open":
                _error(session, command_id, origin, failure, target=f"{session.world.deck_id}/{door.id}")
                return
            session.start_open(command_id, origin, queued_step=False)
        case Verb.STOP | Verb.QUEUE | Verb.STATUS:
            slot = _slot(session, req.args[0])
            if isinstance(slot, Failure):
                _error(session, command_id, origin, slot)
            elif req.verb is Verb.STOP:
                session.stop(command_id, origin)
            else:
                session.emit(command_id, origin, _format_query(session, req.verb), drone=True)
        case _:
            raise ValueError(f"unsupported application request {req.verb!r}")


def _format_query(session: Session, verb: Verb) -> str:
    drone, order = session.world.drone, session.order
    submitted = order.current.submitted_slot if order else "none"
    detail = (f"{drone.display_name} [{drone.permanent_id}; current slot {drone.slot}; "
              f"instruction submitted slot {submitted}]")
    steps = order.instructions[order.index:] if order else ()
    if verb is Verb.QUEUE:
        start = order.index + 1 if order else 1
        lines = [f"{index}. {step.verb} {step.address}" for index, step in enumerate(steps, start)]
        return f"QUEUE: {detail}\n" + ("\n".join(lines) if lines else "empty")
    action = order.phase if order else "idle"
    return (f"STATUS: {detail}; room={drone.room_id}; charge={drone.charge_wh:.6f}/"
            f"{drone.capacity_wh:g} Wh; integrity={drone.condition_pct:g}%; control=player; "
            f"action={action}; queue={len(steps)}; connection=none.")
