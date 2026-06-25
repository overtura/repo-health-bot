import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = load_script("auto_merge_guard")
redteam = load_script("redteam_review")
merge_decision = load_script("merge_decision")


class AutoMergePolicyTest(unittest.TestCase):
    def test_guard_denies_secret_file(self) -> None:
        files = [guard.ChangedFile(path=".env", additions=1, deletions=0)]

        report = guard.evaluate_policy(
            files=files,
            policy=guard.DEFAULT_POLICY,
            base_branch="main",
            head_branch="codex/example",
        )

        self.assertFalse(report["passed"])
        self.assertFalse(report["auto_merge_allowed"])
        self.assertIn("denied pattern", report["hard_failures"][0])

    def test_guard_marks_governance_change_as_manual(self) -> None:
        files = [guard.ChangedFile(path=".github/workflows/auto-merge.yml", additions=20, deletions=0)]

        report = guard.evaluate_policy(
            files=files,
            policy=guard.DEFAULT_POLICY,
            base_branch="main",
            head_branch="codex/example",
        )

        self.assertTrue(report["passed"])
        self.assertFalse(report["auto_merge_allowed"])
        self.assertIn("manual-review pattern", report["manual_reasons"][0])

    def test_redteam_rejects_added_secret(self) -> None:
        guard_report = {
            "passed": True,
            "auto_merge_allowed": True,
            "manual_reasons": [],
            "hard_failures": [],
        }
        sample = "OPENAI" + "_API" + "_KEY" + "=" + "sk-" + "testsecretvalue1234567890"
        diff = f"diff --git a/demo b/demo\n+{sample}\n"

        review = redteam.build_review(guard_report, diff)

        self.assertFalse(review["approved"])
        self.assertEqual(review["risk_level"], "blocker")

    def test_merge_decision_requires_checks_and_guard(self) -> None:
        pr = {
            "isDraft": True,
            "headRefName": "codex/example",
            "baseRefName": "main",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [
                {
                    "name": "test",
                    "workflowName": "CI",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
                {
                    "name": "redteam-review",
                    "workflowName": "Redteam Review",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
            ],
        }
        guard_report = {"passed": True, "auto_merge_allowed": True}

        decision = merge_decision.decide(
            pr,
            guard_report,
            required_checks=["test", "redteam-review"],
        )

        self.assertTrue(decision["should_merge"])


if __name__ == "__main__":
    unittest.main()
