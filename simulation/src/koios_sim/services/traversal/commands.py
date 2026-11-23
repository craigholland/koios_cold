"""Resolve parsed command addresses and format read-only Operations reports."""

from koios_sim.domain.traversal.operation import Failure
from koios_sim.domain.traversal.world import World
from koios_sim.services.traversal.contracts import Instruction, Request, Verb
from koios_sim.services.traversal.snapshots import SessionSnapshot


def target_id(world: World, context: str, kind: str, token: str) -> str | Failure:
    prefix, slash, local = token.partition("/")
    deck, name = (prefix, local) if slash else (context, prefix)
    candidates = (
        (world.door.id,) if kind == "door" else tuple(r.id for r in world.rooms)
    )
    if deck.casefold() == world.deck_id.casefold():
        for candidate in candidates:
            if name.casefold() == candidate.casefold():
                return candidate
    return Failure("E_UNKNOWN_ID", f"Unknown {kind} '{token}' in context '{context}'.")


def assigned_slot(world: World, value: str) -> int | Failure:
    assigned = world.drone.slot
    if value == "all" or value == str(assigned):
        return assigned
    return Failure("E_SLOT", f"Slot {value} is empty or outside the effective team cap.")


def bind_order(world: World, context: str, requests: tuple[Request, ...]) -> tuple[Instruction, ...] | Failure:
    slots = {request.args[0] for request in requests if request.verb is Verb.MOVE}
    if len(slots) != 1 or any(r.verb not in (Verb.MOVE, Verb.OPEN) for r in requests):
        return Failure(
            "E_SEQUENCE",
            "A semicolon sequence must target one assigned drone and contain only drone "
            "actions and supported door requests.",
        )
    targets: list[str] = []
    for req in requests:
        target = target_id(world, context, "room", req.args[1]) if req.verb is Verb.MOVE else target_id(
            world, context, "door", req.args[0]
        )
        if isinstance(target, Failure):
            return target
        targets.append(target)
    slot = assigned_slot(world, slots.pop())
    if isinstance(slot, Failure):
        return slot
    return tuple(Instruction(
        req.verb, target, world.deck_id, world.drone.permanent_id, slot
    ) for req, target in zip(requests, targets, strict=True))


def format_query(snapshot: SessionSnapshot, verb: Verb) -> str:
    drone, order = snapshot.world.drone, snapshot.active
    submitted = order.current.submitted_slot if order else "none"
    detail = (f"{drone.display_name} [{drone.permanent_id}; current slot {drone.slot}; "
              f"instruction submitted slot {submitted}]")
    steps = order.remaining if order else ()
    if verb is Verb.QUEUE:
        start = order.step if order else 1
        lines = [f"{index}. {step.verb} {step.address}" for index, step in enumerate(steps, start)]
        return f"QUEUE: {detail}\n" + ("\n".join(lines) if lines else "empty")
    action = order.phase if order else ("manual" if snapshot.manual_lease is not None else "idle")
    return (f"STATUS: {detail}; room={drone.room_id}; charge={drone.charge_wh:.6f}/"
            f"{drone.capacity_wh:g} Wh; integrity={drone.condition_pct:g}%; control=player; "
            f"action={action}; queue={len(steps)}; connection=none.")
