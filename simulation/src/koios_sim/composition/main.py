"""Compose the developer status process without import-time execution."""

import argparse
import sys

from koios_sim.composition.fixture import FixtureError, load_m0
from koios_sim.interfaces.cli import write_status
from koios_sim.services.traversal.status import get_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Koios's provisional M0 fixture.")
    parser.parse_args()
    try:
        world = load_m0()
    except (FixtureError, OSError) as exc:
        parser.exit(1, f"M0 fixture unavailable: {exc}\n")
    write_status(get_status(world), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
