#!/usr/bin/env python3
import argparse
from projrouter import RouterManager

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("activate")
    a.add_argument("project_name")
    a.add_argument("http_port", type=int)

    d = sub.add_parser("deactivate")
    d.add_argument("project_name")

    sub.add_parser("check")

    args = ap.parse_args()
    mgr = RouterManager(args.registry)

    if args.cmd == "activate":
        mgr.activate(args.project_name, args.http_port)
        print("OK: activated")
    elif args.cmd == "deactivate":
        mgr.deactivate(args.project_name)
        print("OK: deactivated")
    elif args.cmd == "check":
        mgr.check()
        print("OK: check passed")

if __name__ == "__main__":
    main()

