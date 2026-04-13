from __future__ import annotations

import argparse

from pz_agent.openclaw_bridge import rebuild_graph_and_report_from_enriched, rerank_from_enriched_critique
from pz_agent.orchestration import enrich_critique_with_search
from pz_agent.runner import run_pipeline
from pz_agent.visual_benchmark import DEFAULT_BENCHMARK_IDS, build_visual_benchmark_report


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

    visual_benchmark_parser = sub.add_parser("visual-benchmark")
    visual_benchmark_parser.add_argument("--candidate-id", dest="candidate_ids", action="append")
    visual_benchmark_parser.add_argument("--d3tales-path", default="data/d3tales.csv")
    visual_benchmark_parser.add_argument("--out-dir", default="artifacts/visual_benchmark")
    visual_benchmark_parser.add_argument("--model", default="gemini-2.5-flash")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(config_path=args.config, run_dir=args.run_dir)
    elif args.command == "enrich-critique":
        enrich_critique_with_search(run_dir=args.run_dir, config_path=args.config)
    elif args.command == "rebuild-enriched":
        rebuild_graph_and_report_from_enriched(run_dir=args.run_dir)
    elif args.command == "rerank-enriched":
        rerank_from_enriched_critique(run_dir=args.run_dir)
    elif args.command == "visual-benchmark":
        report = build_visual_benchmark_report(
            candidate_ids=args.candidate_ids or list(DEFAULT_BENCHMARK_IDS),
            d3tales_path=args.d3tales_path,
            out_dir=args.out_dir,
            model=args.model,
        )
        print(f"Wrote visual benchmark report to {report['out_dir']}/visual_benchmark.json")


if __name__ == "__main__":
    main()
