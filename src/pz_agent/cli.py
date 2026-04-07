from __future__ import annotations

import argparse

from pz_agent.openclaw_bridge import rebuild_graph_and_report_from_enriched, rerank_from_enriched_critique
from pz_agent.orchestration import enrich_critique_with_search
from pz_agent.runner import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="pz-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("config")
    run_parser.add_argument("--run-dir", default="artifacts/run")

    enrich_parser = sub.add_parser("enrich-critique")
    enrich_parser.add_argument("config")
    enrich_parser.add_argument("--run-dir", default="artifacts/run")

    rebuild_parser = sub.add_parser("rebuild-enriched")
    rebuild_parser.add_argument("--run-dir", default="artifacts/run")

    rerank_parser = sub.add_parser("rerank-enriched")
    rerank_parser.add_argument("--run-dir", default="artifacts/run")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(config_path=args.config, run_dir=args.run_dir)
    elif args.command == "enrich-critique":
        enrich_critique_with_search(run_dir=args.run_dir, config_path=args.config)
    elif args.command == "rebuild-enriched":
        rebuild_graph_and_report_from_enriched(run_dir=args.run_dir)
    elif args.command == "rerank-enriched":
        rerank_from_enriched_critique(run_dir=args.run_dir)


if __name__ == "__main__":
    main()
