"""`iom-cli` — argparse CLI for iocs_monitor's headless API.

Same operations as the Flask REST endpoints, callable from a shell:

    iom-cli list [--category TXM] [--json]
    iom-cli categories [--json]
    iom-cli status <ioc> [--json]
    iom-cli start <ioc>
    iom-cli stop <ioc>
    iom-cli restart <ioc>
    iom-cli medm <ioc>
    iom-cli gui <ioc>

`--json` on read commands emits a machine-readable payload for
scripts / agents. Nonzero exit on failure so shell chains do the
right thing. The Flask web server (`iom`) is unaffected."""
from __future__ import annotations

import argparse
import json
import sys

from . import headless as h


def _emit(payload, as_json: bool, human=None) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return
    if human is not None:
        human(payload)
    else:
        print(payload)


# ── read commands ────────────────────────────────────────────────────

def _cmd_list(args) -> int:
    rows = h.list_iocs(category=args.category)
    if not rows:
        print("(no IOCs match)", file=sys.stderr)
        return 1
    if args.json:
        _emit(rows, True); return 0
    w = max(len(r["name"]) for r in rows)
    for r in rows:
        gui_tag = "  [GUI]" if r["is_gui"] else ""
        desc = f"  — {r['description']}" if r["description"] else ""
        print(f"  {r['name']:<{w}}  [{r['category']}]"
              f"  script={r['script']}{gui_tag}{desc}")
    return 0


def _cmd_categories(args) -> int:
    cats = h.list_categories()
    if args.json:
        _emit(cats, True); return 0
    for c in cats:
        print(f"  {c}")
    return 0


def _cmd_status(args) -> int:
    st = h.get_status(args.ioc, timeout=args.timeout)
    if args.json:
        _emit({"ioc": args.ioc, **st}, True); return 0
    print(f"  {args.ioc}: status={st['status']}  address={st['address']}")
    err = st["status"].startswith("error") or st["status"] in (
        "unavailable", "not found")
    return 1 if err else 0


# ── control commands ────────────────────────────────────────────────

def _do_action(args, fn, label: str) -> int:
    r = fn(args.ioc)
    if "error" in r:
        print(f"  {label} {args.ioc} FAILED: {r['error']}", file=sys.stderr)
        return 1
    print(f"  {label} {args.ioc}: submitted ({r['script']})")
    return 0


def _cmd_start(args)   -> int: return _do_action(args, h.start_ioc,   "start")
def _cmd_stop(args)    -> int: return _do_action(args, h.stop_ioc,    "stop")
def _cmd_restart(args) -> int: return _do_action(args, h.restart_ioc, "restart")
def _cmd_medm(args)    -> int: return _do_action(args, h.medm,        "medm")
def _cmd_gui(args)     -> int: return _do_action(args, h.start_gui,   "gui")


# ── argparse tree ────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="iom-cli",
        description="Headless CLI for iocs_monitor (list / status / "
                    "start / stop / restart / medm / gui).")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON on read commands.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="List every IOC in the config")
    p.add_argument("--category", default=None,
                   help="Filter to a single category (e.g. TXM)")
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("categories", help="List every category name")
    p.set_defaults(func=_cmd_categories)

    p = sub.add_parser("status", help="Scrape the CGI status for an IOC")
    p.add_argument("ioc")
    p.add_argument("--timeout", type=float, default=5.0)
    p.set_defaults(func=_cmd_status)

    for name, fn in [("start", _cmd_start), ("stop", _cmd_stop),
                     ("restart", _cmd_restart), ("medm", _cmd_medm),
                     ("gui", _cmd_gui)]:
        p = sub.add_parser(name, help=f"{name} the IOC via its .sh script")
        p.add_argument("ioc")
        p.set_defaults(func=fn)

    return ap


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
