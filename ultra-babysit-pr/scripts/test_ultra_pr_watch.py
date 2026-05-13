import argparse
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("ultra_pr_watch.py")
MODULE_SPEC = importlib.util.spec_from_file_location("ultra_pr_watch", MODULE_PATH)
ultra_pr_watch = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(ultra_pr_watch)


def sample_pr():
    return {
        "number": 123,
        "url": "https://github.com/openai/codex/pull/123",
        "repo": "openai/codex",
        "head_sha": "abc123",
        "head_branch": "feature",
        "state": "OPEN",
        "merged": False,
        "closed": False,
        "mergeable": "MERGEABLE",
        "merge_state_status": "CLEAN",
        "review_decision": "",
    }


def sample_checks(**overrides):
    checks = {
        "pending_count": 0,
        "failed_count": 0,
        "passed_count": 12,
        "all_terminal": True,
    }
    checks.update(overrides)
    return checks


class UltraPrWatchTests(unittest.TestCase):
    def test_pending_review_items_survive_until_marked_handled(self):
        state = {
            "handled_review_item_ids": [],
            "pending_review_items": [
                {"id": "issue_comment:1", "kind": "issue_comment", "created_at": "2026-01-01T00:00:00Z"}
            ],
        }

        pending = ultra_pr_watch.merge_pending_review_items(state, [])

        self.assertEqual([item["id"] for item in pending], ["issue_comment:1"])

        state["handled_review_item_ids"] = ["issue_comment:1"]
        pending = ultra_pr_watch.merge_pending_review_items(state, [])

        self.assertEqual(pending, [])

    def test_unresolved_review_thread_disappears_when_no_longer_current(self):
        state = {
            "handled_review_item_ids": [],
            "pending_review_items": [
                {"id": "review_thread:abc", "kind": "review_thread", "created_at": "2026-01-01T00:00:00Z"}
            ],
        }

        pending = ultra_pr_watch.merge_pending_review_items(state, [])

        self.assertEqual(pending, [])

    def test_recommend_actions_prioritizes_review_items_before_ci(self):
        actions = ultra_pr_watch.recommend_actions(
            sample_pr(),
            sample_checks(failed_count=1),
            [{"run_id": 99}],
            [],
            [{"id": "review_thread:1", "kind": "review_thread"}],
            0,
            3,
        )

        self.assertEqual(
            actions,
            ["process_review_items", "diagnose_ci_failure", "retry_failed_checks"],
        )

    def test_ready_to_merge_requires_no_pending_review_items(self):
        self.assertFalse(
            ultra_pr_watch.is_pr_ready_to_merge(
                sample_pr(),
                sample_checks(),
                [{"id": "review_thread:1"}],
            )
        )
        self.assertTrue(ultra_pr_watch.is_pr_ready_to_merge(sample_pr(), sample_checks(), []))

    def test_failed_jobs_include_direct_logs_endpoint(self):
        jobs_by_run = {
            99: [
                {
                    "id": 555,
                    "name": "unit tests",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "https://github.com/openai/codex/actions/runs/99/job/555",
                },
                {"id": 556, "name": "lint", "status": "completed", "conclusion": "success"},
            ]
        }

        with patch.object(ultra_pr_watch, "get_jobs_for_run", lambda repo, run_id: jobs_by_run[run_id]):
            failed_jobs = ultra_pr_watch.failed_jobs_from_workflow_runs(
                "openai/codex",
                [
                    {
                        "id": 99,
                        "name": "CI",
                        "status": "in_progress",
                        "conclusion": "",
                        "head_sha": "abc123",
                    }
                ],
                "abc123",
            )

        self.assertEqual(failed_jobs[0]["logs_endpoint"], "repos/openai/codex/actions/jobs/555/logs")

    def test_mark_handled_removes_pending_item_from_state_file(self):
        pr = sample_pr()
        with self.subTest("state mutation"):
            state = {
                "handled_review_item_ids": [],
                "pending_review_items": [
                    {"id": "issue_comment:1", "kind": "issue_comment"},
                    {"id": "issue_comment:2", "kind": "issue_comment"},
                ],
            }
            with patch.object(ultra_pr_watch, "resolve_pr", lambda *args, **kwargs: pr), \
                patch.object(ultra_pr_watch, "load_state", lambda path: state), \
                patch.object(ultra_pr_watch, "save_state", lambda path, new_state: None):
                result = ultra_pr_watch.mark_handled(
                    argparse.Namespace(
                        pr="123",
                        repo=None,
                        state_file="/tmp/test-ultra-pr-state.json",
                        mark_handled=["issue_comment:1"],
                    )
                )

            self.assertEqual(result["remaining_pending_count"], 1)
            self.assertEqual(state["handled_review_item_ids"], ["issue_comment:1"])
            self.assertEqual(state["pending_review_items"][0]["id"], "issue_comment:2")


if __name__ == "__main__":
    unittest.main()
