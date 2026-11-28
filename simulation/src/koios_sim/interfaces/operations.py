"""Parse the supported Operations grammar without knowing the world."""

from koios_sim.domain.traversal.operation import Failure
from koios_sim.services.traversal.contracts import Feedback, Request, Verb
from koios_sim.services.traversal.session import Session

USAGE: dict[str, tuple[Verb, str, str, int]] = {
    "move": (Verb.MOVE, "move <slot> <room>", "Navigate an assigned drone to a known room.", 2),
    "navigate": (Verb.MOVE, "navigate <slot> <room>", "Alias for move.", 2),
    "open": (Verb.OPEN, "open <door>", "Request an ordinary door opening.", 1),
    "stop": (Verb.STOP, "stop <slot> | stop all", "Cancel current work and queued instructions.", 1),
    "status": (Verb.STATUS, "status <slot> | status all", "Inspect current assigned drone status.", 1),
    "queue": (Verb.QUEUE, "queue show <slot>", "Inspect accepted instructions without changing them.", 2),
    "context": (Verb.CONTEXT, "context <deck-id>", "Set the explicit command deck.", 1),
    "help": (Verb.HELP, "help [<verb>]", "List supported commands or show command usage.", 0),
}


def unknown(token: str) -> Failure:
    return Failure("E_UNKNOWN_COMMAND", f"Unknown command '{token}'. Type help for available commands.")


def parse(source: str) -> tuple[Request, ...] | Failure:
    requests: list[Request] = []
    for segment in source.split(";"):
        tokens = segment.split()
        if not tokens:
            return Failure("E_USAGE", "Usage: help [<verb>]")
        token, *args = tokens
        if token not in USAGE:
            return unknown(token)
        verb, usage, _, count = USAGE[token]
        wrong_arity = len(args) > 1 if verb is Verb.HELP else len(args) != count
        if wrong_arity or (verb is Verb.QUEUE and args[0] != "show"):
            return Failure("E_USAGE", f"Usage: {usage}")
        if verb is Verb.QUEUE:
            args = args[1:]
        if verb in (Verb.MOVE, Verb.STOP, Verb.STATUS, Verb.QUEUE):
            first = args[0]
            all_allowed = verb in (Verb.STOP, Verb.STATUS) and first == "all"
            if not all_allowed and not (first.isascii() and first.isdecimal()):
                return Failure("E_USAGE", f"Usage: {usage}")
        requests.append(Request(verb, tuple(args)))
    return tuple(requests)


def execute(session: Session, source: str, origin: str = "operations") -> tuple[Feedback, ...]:
    parsed = parse(source)
    if isinstance(parsed, Failure):
        return (session.record_command_feedback(origin, f"ERROR {parsed.code}: {parsed.reason}"),)
    if len(parsed) == 1 and parsed[0].verb is Verb.HELP:
        args = parsed[0].args
        if not args:
            text = "COMMANDS Operations: " + ", ".join(sorted(USAGE))
        elif args[0] not in USAGE:
            failure = unknown(args[0])
            text = f"ERROR {failure.code}: {failure.reason}"
        else:
            _, usage, description, _ = USAGE[args[0]]
            text = f"USAGE: {usage}\n{description}"
        return (session.record_command_feedback(origin, text),)
    return session.submit(parsed, origin)
