"""pf-debate-mcp [serve] | build-library | login"""

import argparse
import getpass
import sys


def main() -> None:
    ap = argparse.ArgumentParser(prog="pf-debate-mcp", description="Public Forum debate MCP server")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="run the MCP server on stdio (default)")
    b = sub.add_parser("build-library", help="download and index the OpenCaselist card library (resumable)")
    b.add_argument("--events", default="pf,openev,ld,cx",
                   help="comma list of pf, openev (camp files), ld, cx (policy). Default: all")
    b.add_argument("--min-reads", type=int, default=5,
                   help="LD/Policy cards must have been read by at least this many teams (default 5)")
    b.add_argument("--since", type=int, default=2014, help="skip caselists older than this year")
    b.add_argument("--limit", type=int, help="stop after N cards (for testing)")
    b.add_argument("--quick", action="store_true", help="PF cards only (~25k cards, a few minutes)")
    b.add_argument("--rebuild", action="store_true", help="delete the existing library first")
    sub.add_parser("login", help="log in to OpenCaselist with your Tabroom account")
    args = ap.parse_args()

    if args.cmd == "build-library":
        from . import library

        if args.rebuild:
            library.DB_PATH.unlink(missing_ok=True)
        events = library.PRESETS["quick"][0] if args.quick else [e.strip().lower() for e in args.events.split(",")]
        print(f"Building {library.DB_PATH} from Hugging Face {library.DATASET} ({', '.join(events)}). "
              "Safe to stop and rerun: finished shards are skipped.", flush=True)
        library.build(events, args.min_reads, args.since, args.limit, log=lambda m: print(m, flush=True))
    elif args.cmd == "login":
        from . import caselist

        user = input("Tabroom email: ").strip()
        try:
            caselist.login(user, getpass.getpass("Tabroom password (not stored): "))
        except caselist.CaselistError as e:
            sys.exit(str(e))
        print(f"Logged in. Session saved to {caselist.TOKEN}")
    else:
        from .server import mcp

        mcp.run()
