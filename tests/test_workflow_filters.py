from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from loaring_ops.db import connect, init_db
from loaring_ops.github_project import current_iteration_from_field
from loaring_ops.product_sync import get_contract, now_iso
from loaring_ops.safety import SafetyViolation
from loaring_ops.workflow import (
    announce_doc_edit,
    detect_work_conflicts,
    link_pr_to_project,
    prepare_doc_edit,
    sprint_report,
    validate_checkout_target,
    validate_workflow,
)


class WorkflowFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_db = os.environ.get("LOARING_PRODUCT_OPS_DB")
        os.environ["LOARING_PRODUCT_OPS_DB"] = os.path.join(self.tempdir.name, "test.sqlite")
        conn = connect()
        init_db(conn)
        self._insert_story(conn, 1, "Mine current", ["octo"], "Sprint 2")
        self._insert_story(conn, 2, "Other current", ["hubot"], "Sprint 2")
        self._insert_story(conn, 3, "Mine later", ["octo"], "Sprint 3")
        self._insert_sync_state(conn, "github-stories", "loaring-story/loaring-product", "")
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        if self.previous_db is None:
            os.environ.pop("LOARING_PRODUCT_OPS_DB", None)
        else:
            os.environ["LOARING_PRODUCT_OPS_DB"] = self.previous_db
        self.tempdir.cleanup()

    def test_current_iteration_uses_project_configuration_dates(self) -> None:
        field = {
            "configuration": {
                "iterations": [
                    {"id": "it-1", "title": "Sprint 1", "startDate": "2026-07-01", "duration": 14},
                    {"id": "it-2", "title": "Sprint 2", "startDate": "2026-07-15", "duration": 14},
                ]
            }
        }

        result = current_iteration_from_field(field, today=date(2026, 7, 21))

        self.assertEqual(result["title"], "Sprint 2")
        self.assertEqual(result["endDate"], "2026-07-29")

    @patch("loaring_ops.workflow.infer_project_fields")
    def test_validate_workflow_filters_by_project_sprint_and_assignee(self, infer_project_fields) -> None:
        infer_project_fields.side_effect = self._inference

        result = validate_workflow(sprint="Sprint 2", assignee="octo")

        self.assertEqual(result["sprint"], "Sprint 2")
        self.assertEqual(result["assignee"], "octo")
        self.assertEqual(result["storyCount"], 1)
        self.assertEqual(result["stories"][0]["issueNumber"], 1)

    @patch("loaring_ops.workflow.current_project_iteration")
    @patch("loaring_ops.workflow.infer_project_fields")
    def test_sprint_report_defaults_to_current_project_iteration(
        self,
        infer_project_fields,
        current_project_iteration,
    ) -> None:
        infer_project_fields.side_effect = self._inference
        current_project_iteration.return_value = {
            "id": "it-2",
            "title": "Sprint 2",
            "startDate": "2026-07-15",
            "duration": 14,
            "endDate": "2026-07-29",
        }

        result = sprint_report(assignee="octo")

        self.assertEqual(result["sprint"], "Sprint 2")
        self.assertEqual(result["currentSprint"]["title"], "Sprint 2")
        self.assertEqual(result["assignee"], "octo")
        self.assertEqual(result["storyCount"], 1)

    def test_prepare_doc_edit_returns_github_pr_and_issue_comment_drafts(self) -> None:
        result = prepare_doc_edit(
            story_issue=1,
            target="contract",
            files=["docs/api/auth.api-spec.json"],
            notify_users=["@octo", "hubot", "octo"],
            pr_number=7,
        )

        self.assertEqual(result["target"], "contract")
        self.assertEqual(result["branch"], "docs/1-mine-current-ops-contract")
        self.assertEqual(result["notifyUsers"], ["octo", "hubot"])
        self.assertEqual(result["pr"]["url"], "https://github.com/loaring-story/loaring-product/pull/7")
        self.assertIn("Related #1", result["pr"]["body"])
        self.assertIn("@octo @hubot", result["storyComment"]["body"])
        self.assertIn("docs/api/auth.api-spec.json", result["storyComment"]["body"])

    @patch("loaring_ops.workflow.gh_api_paginated")
    @patch("loaring_ops.workflow.gh_api_post")
    def test_announce_doc_edit_posts_story_issue_comment_when_confirmed(self, gh_api_post, gh_api_paginated) -> None:
        gh_api_paginated.return_value = []
        gh_api_post.return_value = {"id": 11, "html_url": "https://github.com/comment/11"}

        result = announce_doc_edit(
            story_issue=1,
            files=["docs/requirements/story-map.md"],
            notify_users=["octo"],
            apply=True,
            confirm=True,
        )

        self.assertEqual(result["status"], "posted")
        self.assertEqual(result["comment"]["id"], 11)
        gh_api_post.assert_called_once()
        path, payload = gh_api_post.call_args.args
        self.assertEqual(path, "repos/loaring-story/loaring-product/issues/1/comments")
        self.assertIn("@octo", payload["body"])

    @patch("loaring_ops.workflow.gh_api_paginated")
    @patch("loaring_ops.workflow.gh_api_post")
    def test_announce_doc_edit_returns_duplicate_for_existing_comment(self, gh_api_post, gh_api_paginated) -> None:
        prepared = prepare_doc_edit(
            story_issue=1,
            files=["docs/requirements/story-map.md"],
            notify_users=["octo"],
        )
        gh_api_paginated.return_value = [
            {"id": 12, "html_url": "https://github.com/comment/12", "body": prepared["storyComment"]["body"]}
        ]

        result = announce_doc_edit(
            story_issue=1,
            files=["docs/requirements/story-map.md"],
            notify_users=["octo"],
            apply=True,
            confirm=True,
        )

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["comment"]["id"], 12)
        gh_api_post.assert_not_called()

    def test_announce_doc_edit_requires_recent_story_sync_when_confirmed(self) -> None:
        conn = connect()
        conn.execute("DELETE FROM sync_state WHERE source = 'github-stories'")
        conn.commit()
        conn.close()

        with self.assertRaises(SafetyViolation):
            announce_doc_edit(
                story_issue=1,
                files=["docs/requirements/story-map.md"],
                notify_users=["octo"],
                apply=True,
                confirm=True,
            )

    @patch("loaring_ops.workflow.subprocess.run")
    def test_validate_checkout_target_blocks_wrong_repo_for_frontend(self, run) -> None:
        run.return_value.returncode = 0
        run.return_value.stdout = "git@github.com:loaring-story/loaring-backend.git\n"

        result = validate_checkout_target("frontend", cwd="/tmp/loaring-backend")

        self.assertFalse(result["valid"])
        self.assertIn("loaring-frontend", result["blockers"][0])

    @patch("loaring_ops.workflow.subprocess.run")
    def test_validate_checkout_target_accepts_matching_backend_repo(self, run) -> None:
        run.return_value.returncode = 0
        run.return_value.stdout = "https://github.com/loaring-story/loaring-backend.git\n"

        result = validate_checkout_target("backend", cwd="/tmp/loaring-backend")

        self.assertTrue(result["valid"])
        self.assertEqual(result["actualRepo"], "loaring-story/loaring-backend")

    @patch("loaring_ops.workflow.gh_api")
    def test_link_pr_to_project_reads_pr_from_cross_repo(self, gh_api) -> None:
        gh_api.return_value = {
            "title": "Backend signup",
            "state": "open",
            "html_url": "https://github.com/loaring-story/loaring-backend/pull/4",
            "body": "Related #1\n\nBackend implementation.",
        }

        result = link_pr_to_project(
            pr_number=4,
            pr_repo="loaring-story/loaring-backend",
            apply=False,
        )

        self.assertEqual(result["repo"], "loaring-story/loaring-product")
        self.assertEqual(result["prRepo"], "loaring-story/loaring-backend")
        self.assertEqual(result["storyIssue"], 1)
        self.assertEqual(result["status"], "planned")
        gh_api.assert_called_once_with("repos/loaring-story/loaring-backend/pulls/4")

    @patch("loaring_ops.workflow.gh_api")
    def test_detect_work_conflicts_finds_story_and_file_prs(self, gh_api) -> None:
        gh_api.side_effect = [
            {
                "items": [
                    {
                        "number": 4,
                        "title": "Backend signup",
                        "html_url": "https://github.com/loaring-story/loaring-backend/pull/4",
                        "state": "open",
                    }
                ]
            },
            {
                "items": [
                    {
                        "number": 5,
                        "title": "Touch auth spec",
                        "html_url": "https://github.com/loaring-story/loaring-backend/pull/5",
                        "state": "open",
                    }
                ]
            },
        ]

        result = detect_work_conflicts(
            story_issue=1,
            target="backend",
            files=["docs/api/auth.api-spec.json"],
            pr_repos=["loaring-story/loaring-backend"],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["conflictCount"], 2)
        self.assertEqual(result["conflicts"][0]["type"], "story")
        self.assertEqual(result["conflicts"][1]["type"], "file")

    def test_contract_cache_is_scoped_by_repo_and_ref(self) -> None:
        conn = connect()
        self._insert_contract_index(conn, "develop", "docs/api/develop.api-spec.json", "Develop contract")
        self._insert_contract_index(conn, "feature/ref", "docs/api/feature.api-spec.json", "Feature contract")
        conn.commit()
        conn.close()

        develop = get_contract(story_issue=1, ref="develop")
        feature = get_contract(story_issue=1, ref="feature/ref")

        self.assertEqual(develop["apiSpecs"][0]["path"], "docs/api/develop.api-spec.json")
        self.assertEqual(feature["apiSpecs"][0]["path"], "docs/api/feature.api-spec.json")

    def test_init_db_migrates_legacy_product_index_scope(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE api_specs (
              path TEXT PRIMARY KEY,
              domain TEXT,
              title TEXT,
              story_issue INTEGER,
              requirement_ids_json TEXT NOT NULL DEFAULT '[]',
              endpoints_json TEXT NOT NULL DEFAULT '[]',
              lifecycle TEXT,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE requirements (
              requirement_id TEXT PRIMARY KEY,
              title TEXT,
              status TEXT,
              epic TEXT,
              story_issues_json TEXT NOT NULL DEFAULT '[]',
              api_specs_json TEXT NOT NULL DEFAULT '[]',
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO api_specs VALUES ('docs/api/auth.json', 'auth', 'Auth', 1, '[]', '[]', 'accepted', ?)",
            (now_iso(),),
        )
        conn.execute(
            "INSERT INTO requirements VALUES ('REQ-1', 'Signup', 'accepted', 'Auth', '[1]', '[]', ?)",
            (now_iso(),),
        )

        init_db(conn)

        api_columns = {row["name"] for row in conn.execute("PRAGMA table_info(api_specs)").fetchall()}
        req_columns = {row["name"] for row in conn.execute("PRAGMA table_info(requirements)").fetchall()}
        self.assertTrue({"repo", "ref"} <= api_columns)
        self.assertTrue({"repo", "ref"} <= req_columns)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM api_specs").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0], 1)

    def _insert_story(self, conn, issue_number: int, title: str, assignees: list[str], sprint: str) -> None:
        conn.execute(
            """
            INSERT INTO stories (
              repo, issue_number, title, state, url, labels_json,
              assignees_json, body, updated_at, synced_at
            )
            VALUES (?, ?, ?, 'open', ?, '[]', ?, '', '2026-07-21T00:00:00Z', '2026-07-21T00:00:00Z')
            """,
            (
                "loaring-story/loaring-product",
                issue_number,
                title,
                f"https://github.com/loaring-story/loaring-product/issues/{issue_number}",
                json.dumps(assignees),
            ),
        )
        fields = {
            "Status": "Todo",
            "Epic": "Ops",
            "Sprint": sprint,
            "Story Point": 1,
            "Contract Required": "No",
            "Contract Readiness": "Not Required",
            "Implementation Target": "Product",
        }
        conn.execute(
            """
            INSERT INTO project_items (repo, project_number, issue_number, item_id, fields_json, synced_at)
            VALUES (?, 7, ?, ?, ?, '2026-07-21T00:00:00Z')
            """,
            (
                "loaring-story/loaring-product",
                issue_number,
                f"item-{issue_number}",
                json.dumps(fields),
            ),
        )

    def _insert_sync_state(self, conn, source: str, repo: str, ref: str) -> None:
        conn.execute(
            """
            INSERT INTO sync_state (source, repo, ref, last_synced_at)
            VALUES (?, ?, ?, ?)
            """,
            (source, repo, ref, now_iso()),
        )

    def _insert_contract_index(self, conn, ref: str, path: str, title: str) -> None:
        conn.execute(
            """
            INSERT INTO api_specs (
              repo, ref, path, domain, title, story_issue, requirement_ids_json,
              endpoints_json, lifecycle, updated_at
            )
            VALUES ('loaring-story/loaring-product', ?, ?, 'auth', ?, 1, '[]', '[]', 'accepted', ?)
            """,
            (ref, path, title, now_iso()),
        )

    def _inference(self, story_issue: int, repo: str, number: int) -> dict:
        return {
            "storyIssue": story_issue,
            "recommendedFields": {
                "Contract Required": "No",
                "Contract Readiness": "Not Required",
                "Implementation Target": "Product",
            },
            "mismatches": [],
        }


if __name__ == "__main__":
    unittest.main()
