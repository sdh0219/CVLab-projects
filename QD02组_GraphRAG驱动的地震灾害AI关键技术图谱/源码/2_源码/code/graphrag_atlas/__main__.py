from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .pipeline import run_index
from .search import gap_search, global_search, local_search


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="graphrag_atlas",
        description="GraphRAG-style AI disaster risk reduction technology atlas pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Build the evidence graph index.")
    index_parser.add_argument("--config", default="config/ontology.json")
    index_parser.add_argument("--corpus", default="data/corpus/sample")
    index_parser.add_argument("--output", default="outputs/graphrag_index")
    index_parser.add_argument("--max-chunks", type=int, default=None)
    index_parser.add_argument(
        "--extractor",
        choices=["rule", "llm", "hybrid"],
        default=os.environ.get("ATLAS_EXTRACTOR", "rule"),
        help="Extraction backend. rule is offline; llm requires ATLAS_LLM_API_KEY; hybrid merges rule and LLM outputs.",
    )

    global_parser = subparsers.add_parser("global-search", help="Search community reports.")
    global_parser.add_argument("query")
    global_parser.add_argument("--output", default="outputs/graphrag_index")

    local_parser = subparsers.add_parser("local-search", help="Search one entity neighborhood.")
    local_parser.add_argument("entity")
    local_parser.add_argument("--output", default="outputs/graphrag_index")

    gap_parser = subparsers.add_parser("gap-search", help="Find missing evidence for technologies.")
    gap_parser.add_argument("--output", default="outputs/graphrag_index")

    args = parser.parse_args()

    if args.command == "index":
        summary = run_index(
            Path(args.config),
            Path(args.corpus),
            Path(args.output),
            args.extractor,
            args.max_chunks,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.command == "global-search":
        print(json.dumps(global_search(Path(args.output), args.query), ensure_ascii=False, indent=2))
    elif args.command == "local-search":
        print(json.dumps(local_search(Path(args.output), args.entity), ensure_ascii=False, indent=2))
    elif args.command == "gap-search":
        print(json.dumps(gap_search(Path(args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
