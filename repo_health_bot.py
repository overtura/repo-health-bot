from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_IGNORES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
}

TEXT_SUFFIXES = {
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".rs",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

METADATA_FILES = [
    "README.md",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "LICENSE",
]

TODO_PATTERN = re.compile(r"\b(?:TODO|FIXME)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TodoHit:
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class HealthReport:
    root: str
    file_count: int
    text_file_count: int
    line_count: int
    metadata_files: list[str]
    todo_hits: list[TodoHit]


def should_ignore(path: Path) -> bool:
    return any(part in DEFAULT_IGNORES for part in path.parts)


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and not should_ignore(path.relative_to(root)):
            files.append(path)
    return sorted(files)


def read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in METADATA_FILES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def analyze_repository(root: Path) -> HealthReport:
    root = root.resolve()
    files = iter_files(root)
    text_file_count = 0
    line_count = 0
    todo_hits: list[TodoHit] = []

    for path in files:
        content = read_text(path)
        if content is None:
            continue
        text_file_count += 1
        lines = content.splitlines()
        line_count += len(lines)
        for index, line in enumerate(lines, start=1):
            if TODO_PATTERN.search(line):
                todo_hits.append(
                    TodoHit(
                        path=path.relative_to(root).as_posix(),
                        line=index,
                        text=line.strip(),
                    )
                )

    metadata_files = [name for name in METADATA_FILES if (root / name).exists()]

    return HealthReport(
        root=str(root),
        file_count=len(files),
        text_file_count=text_file_count,
        line_count=line_count,
        metadata_files=metadata_files,
        todo_hits=todo_hits,
    )


def repository_directory(value: str) -> Path:
    path = Path(value)
    try:
        if not path.exists():
            raise argparse.ArgumentTypeError(f"path does not exist: {value!r}")
        if not path.is_dir():
            raise argparse.ArgumentTypeError(f"path is not a directory: {value!r}")
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"invalid path: {value!r}: {exc}") from exc
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a small repository health report.")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=repository_directory,
        help="Repository directory to scan.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    return parser


def to_markdown(report: HealthReport) -> str:
    lines = [
        "# Repository Health Report",
        "",
        f"- Root: `{report.root}`",
        f"- Files: {report.file_count}",
        f"- Text files: {report.text_file_count}",
        f"- Lines: {report.line_count}",
        f"- Metadata files: {', '.join(report.metadata_files) if report.metadata_files else 'none'}",
        f"- TODO/FIXME hits: {len(report.todo_hits)}",
        "",
    ]
    if report.todo_hits:
        lines.append("## TODO/FIXME")
        lines.append("")
        for hit in report.todo_hits:
            lines.append(f"- `{hit.path}:{hit.line}` {hit.text}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args()

    report = analyze_repository(args.path)
    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print(to_markdown(report))


if __name__ == "__main__":
    main()
