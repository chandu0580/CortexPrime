"""CLI entry point for the architecture gate.

    python -m backend.platform.architecture             # text report
    python -m backend.platform.architecture --markdown  # PR comment
    python -m backend.platform.architecture --json      # machine readable

Exit codes: ``0`` gate passed, ``1`` blocking violation, ``2`` the run itself
failed. CI reads the exit code; a human reads the report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.platform.architecture.architecture_report import (
    render_markdown,
    render_text,
    to_dict,
)
from backend.platform.architecture.fitness_functions import default_suite
from backend.platform.architecture.invariant_tests import constitutional_invariants
from backend.platform.architecture.rules import ModuleGraph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="package root to analyse (default: backend/)",
    )
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--markdown", action="store_true")
    fmt.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="write the report to a file")
    args = parser.parse_args(argv)

    try:
        graph = ModuleGraph.build(args.root)
        suite = default_suite()
        result = suite.run(graph)
    except Exception as exc:  # noqa: BLE001 - a failed run is distinct from a failed gate
        print(f"architecture analysis failed: {exc}", file=sys.stderr)
        return 2

    invariants = constitutional_invariants()
    if args.json:
        report = json.dumps(to_dict(result, graph=graph, invariants=invariants), indent=2)
    elif args.markdown:
        report = render_markdown(result, graph=graph, invariants=invariants)
    else:
        report = render_text(result, graph=graph, invariants=invariants)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"report written to {args.output}")
    else:
        print(report)

    return 0 if result.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
