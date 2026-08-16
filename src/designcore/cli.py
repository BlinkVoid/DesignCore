"""designcore command line entry point."""

from __future__ import annotations

import argparse
import sys

from designcore.doctor import check_backends


def _cmd_doctor(_args: argparse.Namespace) -> int:
    statuses = check_backends()
    missing = 0
    for status in statuses:
        if status.available:
            print(f"  ok       {status.backend.name:<10} {status.path}")
        else:
            missing += 1
            print(f"  MISSING  {status.backend.name:<10} {status.backend.purpose}")
            print(f"           install: {status.backend.install_hint}")
    if missing:
        print(f"\n{missing} backend(s) missing. Diagrams cannot be verified without them.")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="designcore")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="Report render backend availability")
    doctor.set_defaults(func=_cmd_doctor)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
