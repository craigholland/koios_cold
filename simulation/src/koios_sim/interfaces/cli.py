"""Developer-only status output; not the player command parser."""

import json
from dataclasses import asdict
from typing import TextIO

from koios_sim.services.traversal.status import StatusSnapshot


def write_status(snapshot: StatusSnapshot, stream: TextIO) -> None:
    json.dump(asdict(snapshot), stream, indent=2, allow_nan=False)
    stream.write("\n")
