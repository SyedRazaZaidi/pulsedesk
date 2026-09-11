from __future__ import annotations

import argparse

from pulsedesk.config import DB_PATH
from pulsedesk.db import init_db
from pulsedesk.seed import seed
from pulsedesk.train import train


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pulsedesk", description="Demand desk: seed, train, serve.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="Write SQLite catalog + daily demand")
    sub.add_parser("train", help="Fit quantiles, eval vs seasonal naive, write recs")
    serve = sub.add_parser("serve", help="Open the ops desk")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8010)
    sub.add_parser("all", help="seed → train")
    args = parser.parse_args(argv)

    if args.cmd == "seed":
        seed()
        print(f"db → {DB_PATH}")
    elif args.cmd == "train":
        train()
    elif args.cmd == "all":
        seed()
        train()
    elif args.cmd == "serve":
        import uvicorn

        from pulsedesk.serve.app import create_app

        init_db()
        uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
