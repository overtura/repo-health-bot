from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_POLICY = {
    "level": 3,
    "max_changed_files": 20,
    "max_total_additions": 1200,
    "max_total_deletions": 800,
    "allow_binary_files": False,
    "allowed_base_branches": ["main"],
    "auto_merge_head_prefixes": ["codex/", "self-improve/"],
    "deny_patterns": [
        ".env",
        ".env.*",
        "**/*.pem",
        "**/*.key",
        "**/*.p12",
        "**/*.pfx",
        "**/id_rsa",
        "**/id_ed25519",
        "**/.npmrc",
        "**/.pypirc",
    ],
    "manual_review_patterns": [
        ".github/workflows/**",
        "policies/auto_merge.json",
        "scripts/auto_merge_guard.py",
        "scripts/merge_decision.py",
        "scripts/redteam_review.py",
    ],
}


@dataclass(frozen=True)
class ChangedFile:
    path: str
    additions: int
    deletions: int
    binary: bool = False


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


def load_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_POLICY)
    with path.open(encoding="utf-8") as file:
        policy = json.load(file)
    merged = dict(DEFAULT_POLICY)
    merged.update(policy)
    return merged


def matches_pattern(path: str, pattern: str) -> bool:
    normalized_path = path.replace("\\", "/")
    normalized_pattern = pattern.replace("\\", "/")
    if normalized_pattern.endswith("/**"):
        prefix = normalized_pattern[:-3]
        return normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
    return fnmatch.fnmatchcase(normalized_path, normalized_pattern)


def any_match(path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if matches_pattern(path, pattern):
            return pattern
    return None


def changed_files(base_ref: str, head_ref: str) -> list[ChangedFile]:
    output = run_git(["diff", "--numstat", f"{base_ref}...{head_ref}"])
    files: list[ChangedFile] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        raw_additions, raw_deletions, path = parts[0], parts[1], parts[-1]
        binary = raw_additions == "-" or raw_deletions == "-"
        additions = 0 if binary else int(raw_additions)
        deletions = 0 if binary else int(raw_deletions)
        files.append(ChangedFile(path=path, additions=additions, deletions=deletions, binary=binary))
    return files


def evaluate_policy(
    *,
    files: list[ChangedFile],
    policy: dict[str, Any],
    base_branch: str,
    head_branch: str,
) -> dict[str, Any]:
    hard_failures: list[str] = []
    manual_reasons: list[str] = []
    warnings: list[str] = []

    total_additions = sum(file.additions for file in files)
    total_deletions = sum(file.deletions for file in files)

    if base_branch not in policy["allowed_base_branches"]:
        manual_reasons.append(f"base branch is not auto-merge enabled: {base_branch}")

    if not any(head_branch.startswith(prefix) for prefix in policy["auto_merge_head_prefixes"]):
        manual_reasons.append(f"head branch does not use an auto-merge prefix: {head_branch}")

    if len(files) > policy["max_changed_files"]:
        hard_failures.append(
            f"changed file count {len(files)} exceeds limit {policy['max_changed_files']}"
        )

    if total_additions > policy["max_total_additions"]:
        hard_failures.append(
            f"added line count {total_additions} exceeds limit {policy['max_total_additions']}"
        )

    if total_deletions > policy["max_total_deletions"]:
        hard_failures.append(
            f"deleted line count {total_deletions} exceeds limit {policy['max_total_deletions']}"
        )

    for file in files:
        denied_pattern = any_match(file.path, policy["deny_patterns"])
        if denied_pattern:
            hard_failures.append(f"{file.path} matches denied pattern {denied_pattern}")

        manual_pattern = any_match(file.path, policy["manual_review_patterns"])
        if manual_pattern:
            manual_reasons.append(f"{file.path} matches manual-review pattern {manual_pattern}")

        if file.binary and not policy["allow_binary_files"]:
            hard_failures.append(f"{file.path} is a binary change")

    if not files:
        warnings.append("no changed files found")
        manual_reasons.append("empty diff is not auto-merged")

    passed = not hard_failures
    auto_merge_allowed = passed and not manual_reasons

    return {
        "passed": passed,
        "auto_merge_allowed": auto_merge_allowed,
        "level": policy["level"],
        "base_branch": base_branch,
        "head_branch": head_branch,
        "changed_files": [asdict(file) for file in files],
        "file_count": len(files),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "hard_failures": hard_failures,
        "manual_reasons": manual_reasons,
        "warnings": warnings,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Auto Merge Guard",
        "",
        f"- Passed: `{report['passed']}`",
        f"- Auto merge allowed: `{report['auto_merge_allowed']}`",
        f"- Level: `{report['level']}`",
        f"- Base branch: `{report['base_branch']}`",
        f"- Head branch: `{report['head_branch']}`",
        f"- Changed files: `{report['file_count']}`",
        f"- Additions: `{report['total_additions']}`",
        f"- Deletions: `{report['total_deletions']}`",
        "",
    ]
    if report["hard_failures"]:
        lines.extend(["## Hard Failures", ""])
        lines.extend(f"- {item}" for item in report["hard_failures"])
        lines.append("")
    if report["manual_reasons"]:
        lines.extend(["## Manual Review Reasons", ""])
        lines.extend(f"- {item}" for item in report["manual_reasons"])
        lines.append("")
    if report["warnings"]:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in report["warnings"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate whether a PR is safe for auto-merge.")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--head-branch", default="")
    parser.add_argument("--policy", default="policies/auto_merge.json")
    parser.add_argument("--output", default="")
    parser.add_argument("--summary-md", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    policy = load_policy(Path(args.policy))
    files = changed_files(args.base_ref, args.head_ref)
    report = evaluate_policy(
        files=files,
        policy=policy,
        base_branch=args.base_branch,
        head_branch=args.head_branch,
    )

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    print(payload)

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    if args.summary_md:
        write_markdown(report, Path(args.summary_md))

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
