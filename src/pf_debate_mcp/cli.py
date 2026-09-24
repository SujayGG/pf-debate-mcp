"""pf-debate-mcp [serve] | build-library | login"""

import argparse
import getpass
import sys


def main() -> None:
    ap = argparse.ArgumentParser(prog="pf-debate-mcp", description="Public Forum debate MCP server")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="run the MCP server on stdio (default)")
    b = sub.add_parser("build-library",
                       help="install the card library (downloads the prebuilt one; resumable)")
    b.add_argument("--from-source", action="store_true",
                   help="build from the raw OpenCaselist dataset instead of downloading (hours)")
    b.add_argument("--events", default="pf,openev,ld,cx",
                   help="from-source: comma list of pf, openev (camp files), ld, cx (policy). Default: all")
    b.add_argument("--min-reads", type=int, default=5,
                   help="from-source: LD/Policy cards must have been read by at least this many teams")
    b.add_argument("--since", type=int, default=2014, help="from-source: skip caselists older than this year")
    b.add_argument("--limit", type=int, help="from-source: stop after N cards (for testing)")
    b.add_argument("--quick", action="store_true", help="from-source: PF cards only (a few minutes)")
    b.add_argument("--rebuild", action="store_true", help="from-source: delete the existing build first")
    sub.add_parser("login", help="log in to OpenCaselist with your Tabroom account")
    args = ap.parse_args()

    if args.cmd == "build-library":
        from . import library

        log = lambda m: print(m, flush=True)  # noqa: E731
        if not (args.from_source or args.quick):
            try:
                library.download(log=log)
            except Exception as e:  # network, checksum, or disk problems: all end the command the same way
                sys.exit(f"Library download failed: {e}\nRerun to resume, or use --from-source.")
            return
        if args.rebuild:
            library.SOURCE_DB.unlink(missing_ok=True)
        events = library.PRESETS["quick"][0] if args.quick else [e.strip().lower() for e in args.events.split(",")]
        log(f"Building {library.SOURCE_DB} from Hugging Face {library.DATASET} ({', '.join(events)}). "
            "Safe to stop and rerun: finished shards are skipped.")
        library.build(events, args.min_reads, args.since, args.limit, log=log)
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
