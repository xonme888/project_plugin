from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from loaring_ops.db import connect, init_db
from loaring_ops.github_project import current_iteration_from_field
from loaring_ops.workflow import sprint_report, validate_workflow


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
