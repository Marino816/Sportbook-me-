from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isolated SB ME Market Tools Odds API snapshot.")
    parser.add_argument("command", choices=["configure", "fetch", "serve"])
    args, rest = parser.parse_known_args(argv)
    if args.command == "configure":
        from market_snapshot.access import main as cmd
        return cmd()
    if args.command == "fetch":
        from market_snapshot.bounded_fetch import main as cmd
        return cmd()
    from market_snapshot.serve import main as cmd
    return cmd(rest)


if __name__ == "__main__":
    raise SystemExit(main())
