from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from maintainer_bot.config import Settings
from maintainer_bot.github_api import upsert_issue_comment
from maintainer_bot.llm import LlmConfig, call_openai_text


MARKER = "<!-- maintainer-bot:pr-summary -->"


@dataclass(frozen=True)
class ChangedFile:
    path: str
    additions: int
    deletions: int


def collect_changed_files(*, base_ref: str, head_ref: str) -> list[ChangedFile]:
    output = subprocess.check_output(
        ["git", "diff", "--numstat", f"{base_ref}...{head_ref}"],
        text=True,
        encoding="utf-8",
    )
    changed: list[ChangedFile] = []
    for raw_line in output.splitlines():
        parts = raw_line.split("\t")
        if len(parts) < 3:
            continue
        additions_raw, deletions_raw, path = parts[0], parts[1], parts[2]
        additions = int(additions_raw) if additions_raw.isdigit() else 0
        deletions = int(deletions_raw) if deletions_raw.isdigit() else 0
        changed.append(ChangedFile(path=path, additions=additions, deletions=deletions))
    return changed


def collect_diff(*, base_ref: str, head_ref: str, max_chars: int = 12000) -> str:
    diff = subprocess.check_output(
        ["git", "diff", "--unified=3", f"{base_ref}...{head_ref}"],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if len(diff) <= max_chars:
        return diff
    return diff[:max_chars] + "\n\n[diff truncated]\n"


def render_static_summary(changed_files: list[ChangedFile]) -> str:
    total_additions = sum(item.additions for item in changed_files)
    total_deletions = sum(item.deletions for item in changed_files)
    lines = [
        MARKER,
        "## Maintainer Bot PR 요약",
        "",
        f"- 변경 파일 수: {len(changed_files)}",
        f"- 추가 라인 수: {total_additions}",
        f"- 삭제 라인 수: {total_deletions}",
        "",
        "### 변경 파일",
        "",
    ]
    if not changed_files:
        lines.append("감지된 파일 변경이 없습니다.")
    else:
        for item in changed_files[:30]:
            lines.append(f"- `{item.path}` (+{item.additions}/-{item.deletions})")
        if len(changed_files) > 30:
            lines.append(f"- ...외 {len(changed_files) - 30}개 파일")

    lines.extend(
        [
            "",
            "### 리뷰 체크리스트",
            "",
            "- [ ] eval 변경이 의도된 것이며 설명 없이 약화되지 않았습니다.",
            "- [ ] workflow 권한 변경이 최소 범위입니다.",
            "- [ ] 생성된 제안 파일을 merge 전에 검토했습니다.",
        ]
    )
    return "\n".join(lines)


def render_openai_summary(
    *,
    settings: Settings,
    changed_files: list[ChangedFile],
    diff: str,
) -> str:
    instructions = """You summarize pull requests for maintainers.

Write the summary in Korean by default. Keep commands, file paths, labels, and code identifiers unchanged.

Return concise Markdown with:

- 요약
- 주요 파일
- 위험
- 검증 제안

Be specific. Do not claim tests passed unless the diff shows it."""
    user_input = json.dumps(
        {
            "changed_files": [item.__dict__ for item in changed_files],
            "diff": diff,
        },
        ensure_ascii=False,
    )
    summary = call_openai_text(
        api_key=settings.openai_api_key or "",
        config=LlmConfig(model=settings.model, reasoning_effort=settings.reasoning_effort),
        instructions=instructions,
        user_input=user_input,
    )
    return f"{MARKER}\n## Maintainer Bot PR 요약\n\n{summary.strip()}\n"


def write_pr_summary(
    *,
    settings: Settings,
    base_ref: str,
    head_ref: str,
    output_path: Path,
    use_openai: bool,
) -> Path:
    changed_files = collect_changed_files(base_ref=base_ref, head_ref=head_ref)
    if use_openai and settings.openai_api_key:
        diff = collect_diff(base_ref=base_ref, head_ref=head_ref)
        body = render_openai_summary(settings=settings, changed_files=changed_files, diff=diff)
    else:
        body = render_static_summary(changed_files)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body.strip() + "\n", encoding="utf-8")
    return output_path


def comment_pr_summary(
    *,
    repo: str,
    pr_number: int,
    token: str,
    summary_path: Path,
) -> str:
    body = summary_path.read_text(encoding="utf-8")
    if MARKER not in body:
        body = f"{MARKER}\n{body}"
    return upsert_issue_comment(
        repo=repo,
        issue_number=pr_number,
        token=token,
        marker=MARKER,
        body=body,
    )
