from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*['\"]?[^'\"\s]+"),
]

RISKY_WORKFLOW_PATTERNS = [
    re.compile(r"pull_request_target"),
    re.compile(r"permissions:\s*write-all"),
    re.compile(r"gh\s+pr\s+merge\s+.*--admin"),
]


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def added_lines_with_paths(diff_text: str) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    current_path = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_path = line[6:]
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append((current_path, line[1:]))
    return lines


def deleted_lines(diff_text: str) -> list[str]:
    lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            lines.append(line[1:])
    return lines


def latest_diff(base_ref: str, head_ref: str) -> str:
    return run_git(["diff", "--unified=0", f"{base_ref}...{head_ref}"])


def build_review(guard_report: dict[str, Any], diff_text: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    added = added_lines_with_paths(diff_text)
    deleted = deleted_lines(diff_text)

    if not guard_report.get("passed", False):
        for issue in guard_report.get("hard_failures", []):
            findings.append(
                {
                    "severity": "blocker",
                    "title": "Guard policy failed",
                    "details": issue,
                }
            )

    for path, line in added:
        if path != "scripts/redteam_review.py":
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "severity": "blocker",
                            "title": "Possible secret added",
                            "details": f"A newly added line in `{path or 'unknown'}` looks like a credential.",
                        }
                    )
                    break

        if path.startswith(".github/workflows/"):
            for pattern in RISKY_WORKFLOW_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "severity": "blocker",
                            "title": "Risky workflow automation added",
                            "details": f"`{path}` contains new content matching `{pattern.pattern}`.",
                        }
                    )
                    break

    removed_test_lines = [
        line
        for line in deleted
        if ("assert" in line or "unittest" in line or "pytest" in line)
    ]
    if len(removed_test_lines) >= 8:
        findings.append(
            {
                "severity": "high",
                "title": "Large test weakening signal",
                "details": "Many assertion or test framework lines were removed.",
            }
        )

    if guard_report.get("manual_reasons"):
        findings.append(
            {
                "severity": "medium",
                "title": "Manual merge recommended",
                "details": "; ".join(guard_report["manual_reasons"]),
            }
        )

    blocker_count = sum(1 for finding in findings if finding["severity"] == "blocker")
    high_count = sum(1 for finding in findings if finding["severity"] == "high")
    approved = blocker_count == 0

    if blocker_count:
        risk_level = "blocker"
    elif high_count:
        risk_level = "high"
    elif guard_report.get("manual_reasons"):
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "approved": approved,
        "reviewer": "repo-health-bot-redteam",
        "mode": "deterministic-level-3",
        "risk_level": risk_level,
        "summary": (
            "Redteam approved this change."
            if approved
            else "Redteam found blocker-level risk and rejected this change."
        ),
        "findings": findings,
        "guard_passed": guard_report.get("passed", False),
        "auto_merge_allowed": guard_report.get("auto_merge_allowed", False),
    }


def write_markdown(review: dict[str, Any], path: Path) -> None:
    lines = [
        "# Redteam Review",
        "",
        f"- Approved: `{review['approved']}`",
        f"- Mode: `{review['mode']}`",
        f"- Risk level: `{review['risk_level']}`",
        f"- Auto merge allowed: `{review['auto_merge_allowed']}`",
        "",
        review["summary"],
        "",
    ]
    if review["findings"]:
        lines.extend(["## Findings", ""])
        for finding in review["findings"]:
            lines.append(f"- **{finding['severity']}** {finding['title']}: {finding['details']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the required redteam review gate.")
    parser.add_argument("--guard-report", required=True)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--output", default="")
    parser.add_argument("--summary-md", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard_report = json.loads(Path(args.guard_report).read_text(encoding="utf-8"))
    diff_text = latest_diff(args.base_ref, args.head_ref)
    review = build_review(guard_report, diff_text)

    payload = json.dumps(review, indent=2, ensure_ascii=False)
    print(payload)

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    if args.summary_md:
        write_markdown(review, Path(args.summary_md))

    return 0 if review["approved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
