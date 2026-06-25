from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def check_name(check: dict[str, Any]) -> str:
    workflow = check.get("workflowName")
    name = check.get("name", "")
    return f"{workflow} / {name}" if workflow else name


def successful_checks(pr: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for check in pr.get("statusCheckRollup", []):
        if check.get("status") == "COMPLETED" and check.get("conclusion") == "SUCCESS":
            names.add(check.get("name", ""))
            names.add(check_name(check))
    return names


def decide(pr: dict[str, Any], guard: dict[str, Any], required_checks: list[str]) -> dict[str, Any]:
    reasons: list[str] = []
    successes = successful_checks(pr)

    if not guard.get("passed", False):
        reasons.append("auto-merge guard did not pass")

    if not guard.get("auto_merge_allowed", False):
        reasons.extend(guard.get("manual_reasons", ["auto-merge guard requires manual review"]))

    missing_checks = [check for check in required_checks if check not in successes]
    if missing_checks:
        reasons.append(f"missing successful required checks: {', '.join(missing_checks)}")

    if pr.get("mergeStateStatus") == "DIRTY":
        reasons.append("pull request has merge conflicts")

    return {
        "should_merge": not reasons,
        "reasons": reasons,
        "successful_checks": sorted(successes),
        "head_ref": pr.get("headRefName"),
        "base_ref": pr.get("baseRefName"),
        "is_draft": pr.get("isDraft", False),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decide whether auto-merge may run.")
    parser.add_argument("--pr-json", required=True)
    parser.add_argument("--guard-report", required=True)
    parser.add_argument("--required-check", action="append", default=[])
    parser.add_argument("--output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pr = json.loads(Path(args.pr_json).read_text(encoding="utf-8"))
    guard = json.loads(Path(args.guard_report).read_text(encoding="utf-8"))
    decision = decide(pr, guard, args.required_check)

    payload = json.dumps(decision, indent=2, ensure_ascii=False)
    print(payload)

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
