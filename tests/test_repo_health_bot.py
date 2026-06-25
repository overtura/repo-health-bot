import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from repo_health_bot import analyze_repository, build_parser, to_markdown


class RepoHealthBotTest(unittest.TestCase):
    def test_analyze_repository_counts_todo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            (tmp_path / "README.md").write_text("# Demo\n\nTODO: add usage\n", encoding="utf-8")
            (tmp_path / "data.bin").write_bytes(b"\x00\x01")

            report = analyze_repository(tmp_path)

            self.assertEqual(report.file_count, 2)
            self.assertEqual(report.text_file_count, 1)
            self.assertEqual(report.line_count, 3)
            self.assertEqual(report.metadata_files, ["README.md"])
            self.assertEqual(len(report.todo_hits), 1)
            self.assertEqual(report.todo_hits[0].path, "README.md")

    def test_to_markdown_includes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

            report = analyze_repository(tmp_path)
            markdown = to_markdown(report)

            self.assertIn("# Repository Health Report", markdown)
            self.assertIn("Metadata files: README.md", markdown)

    def test_parser_rejects_missing_path(self) -> None:
        parser = build_parser()
        stderr = io.StringIO()

        with (
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as caught,
        ):
            parser.parse_args(["does-not-exist"])

        self.assertEqual(caught.exception.code, 2)
        self.assertIn("path does not exist", stderr.getvalue())

    def test_parser_rejects_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            readme_path = tmp_path / "README.md"
            readme_path.write_text("# Demo\n", encoding="utf-8")
            parser = build_parser()
            stderr = io.StringIO()

            with (
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit) as caught,
            ):
                parser.parse_args([str(readme_path)])

            self.assertEqual(caught.exception.code, 2)
            self.assertIn("path is not a directory", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
