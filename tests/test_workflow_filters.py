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
from loaring_ops.mcp_tools import call_tool
from loaring_ops.product_sync import get_api_spec, get_contract, now_iso, resolve_contract_target
from loaring_ops.safety import SafetyViolation
from loaring_ops.telemetry import (
    extract_bottleneck_events,
    insert_events,
    weekly_bottleneck_report,
)
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
        self.previous_telemetry_db = os.environ.get("LOARING_PRODUCT_OPS_TELEMETRY_DB")
        os.environ["LOARING_PRODUCT_OPS_DB"] = os.path.join(self.tempdir.name, "test.sqlite")
        os.environ["LOARING_PRODUCT_OPS_TELEMETRY_DB"] = os.path.join(self.tempdir.name, "telemetry.sqlite")
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
        if self.previous_telemetry_db is None:
            os.environ.pop("LOARING_PRODUCT_OPS_TELEMETRY_DB", None)
        else:
            os.environ["LOARING_PRODUCT_OPS_TELEMETRY_DB"] = self.previous_telemetry_db
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

    @patch("loaring_ops.workflow.sync_stories")
    def test_announce_doc_edit_reports_recovery_when_story_cache_was_stale(self, sync_stories) -> None:
        def mark_synced(repo: str) -> dict:
            conn = connect()
            self._insert_sync_state(conn, "github-stories", repo, "")
            conn.commit()
            conn.close()
            return {"status": "synced"}

        sync_stories.side_effect = mark_synced
        conn = connect()
        conn.execute("DELETE FROM sync_state WHERE source = 'github-stories'")
        conn.commit()
        conn.close()

        with patch("loaring_ops.workflow.gh_api_paginated", return_value=[]), patch(
            "loaring_ops.workflow.gh_api_post",
            return_value={"id": 11, "html_url": "https://github.com/comment/11"},
        ):
            result = announce_doc_edit(
                story_issue=1,
                files=["docs/requirements/story-map.md"],
                notify_users=["octo"],
                apply=True,
                confirm=True,
            )

        self.assertEqual(result["status"], "posted")
        self.assertEqual(result["syncRecovery"]["status"], "synced")
        sync_stories.assert_called_once_with(repo="loaring-story/loaring-product")

    @patch("loaring_ops.workflow.sync_stories")
    def test_announce_doc_edit_returns_clear_recovery_instruction_when_sync_fails(self, sync_stories) -> None:
        sync_stories.side_effect = RuntimeError("offline")
        conn = connect()
        conn.execute("DELETE FROM sync_state WHERE source = 'github-stories'")
        conn.commit()
        conn.close()

        with self.assertRaises(SafetyViolation) as raised:
            announce_doc_edit(
                story_issue=1,
                files=["docs/requirements/story-map.md"],
                notify_users=["octo"],
                apply=True,
                confirm=True,
            )
        self.assertIn("Run loaring_sync_stories", str(raised.exception))

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

    def test_resolve_contract_target_maps_legacy_story_to_canonical_contract(self) -> None:
        conn = connect()
        self._insert_figure_storyline_contract_fixture(conn)
        conn.commit()
        conn.close()

        result = resolve_contract_target(story_issue=370)

        self.assertEqual(result["canonicalRepo"], "loaring-story/loaring-product")
        self.assertEqual(result["canonicalStoryIssue"], 3)
        self.assertEqual(result["requirementId"], "REQ-FIGURE-002")
        self.assertEqual(result["apiSpecPath"], "docs/api/370-figure-storyline.api-spec.json")
        self.assertEqual(
            result["endpointIds"],
            ["figure.storyline.create", "figure.storyline.update", "figure.storyline.delete"],
        )
        self.assertEqual(result["legacyIssueReferences"][0]["issue"], 370)
        self.assertIn(result["confidence"], {"high", "medium"})

    def test_resolve_contract_target_from_spec_path(self) -> None:
        conn = connect()
        self._insert_figure_storyline_contract_fixture(conn)
        conn.commit()
        conn.close()

        result = resolve_contract_target(api_spec_path="docs/api/370-figure-storyline.api-spec.json")

        self.assertEqual(result["canonicalStoryIssue"], 3)
        self.assertEqual(result["requirementId"], "REQ-FIGURE-002")
        self.assertEqual(result["endpointIds"][0], "figure.storyline.create")

    def test_get_api_spec_returns_request_response_schema_summary(self) -> None:
        conn = connect()
        self._insert_figure_storyline_contract_fixture(conn)
        conn.commit()
        conn.close()

        result = get_api_spec(path="docs/api/370-figure-storyline.api-spec.json", endpoint_id="figure.storyline.create")

        self.assertEqual(result["path"], "docs/api/370-figure-storyline.api-spec.json")
        self.assertEqual(len(result["endpoints"]), 1)
        endpoint = result["endpoints"][0]
        self.assertEqual(endpoint["request"]["bodySchema"], "StorylineCreateRequest")
        self.assertEqual(endpoint["response"]["bodySchema"], "StorylineResponse")
        self.assertEqual(endpoint["request"]["body"]["fields"][0]["name"], "content")
        self.assertIn("등록 성공 시", result["uiRules"][0])

    def test_extract_bottleneck_events_records_only_structured_bottlenecks(self) -> None:
        normal = extract_bottleneck_events(
            "loaring_resolve_contract_target",
            {"storyIssue": 370},
            {"canonicalStoryIssue": 3, "confidence": "high", "warnings": []},
            None,
            5,
        )
        ambiguous = extract_bottleneck_events(
            "loaring_resolve_contract_target",
            {"storyIssue": 370},
            {
                "canonicalStoryIssue": 3,
                "confidence": "medium",
                "warnings": ["Multiple plausible contract targets matched; use candidates to disambiguate."],
            },
            None,
            5,
        )

        self.assertEqual(normal, [])
        self.assertEqual(ambiguous[0]["eventType"], "target_resolution_ambiguous")
        self.assertEqual(ambiguous[0]["storyIssue"], 370)

    def test_call_tool_logs_missing_api_spec_snapshot_without_blocking_result(self) -> None:
        result = call_tool("loaring_get_api_spec", {"path": "docs/api/missing.api-spec.json"})
        report = weekly_bottleneck_report()

        self.assertEqual(result["status"], "missing")
        self.assertEqual(report["eventCount"], 1)
        self.assertEqual(report["events"][0]["eventType"], "missing_api_spec_snapshot")

    def test_weekly_bottleneck_report_groups_events_and_recommends_fixes(self) -> None:
        insert_events(
            [
                {
                    "id": "event-1",
                    "occurredAt": now_iso(),
                    "toolName": "loaring_resolve_contract_target",
                    "eventType": "target_resolution_ambiguous",
                    "repo": "loaring-story/loaring-product",
                    "storyIssue": 370,
                    "apiSpecPath": "docs/api/370-figure-storyline.api-spec.json",
                    "apply": False,
                    "durationMs": 7,
                    "warningCount": 1,
                    "blockerCount": 0,
                    "summary": "ambiguous",
                    "details": {"warnings": ["ambiguous"]},
                },
                {
                    "id": "event-2",
                    "occurredAt": now_iso(),
                    "toolName": "loaring_get_api_spec",
                    "eventType": "missing_api_spec_snapshot",
                    "repo": "loaring-story/loaring-product",
                    "apply": False,
                    "durationMs": 4,
                    "warningCount": 1,
                    "blockerCount": 0,
                    "summary": "missing",
                    "details": {},
                },
            ]
        )

        report = weekly_bottleneck_report(repo="loaring-story/loaring-product")

        self.assertEqual(report["eventCount"], 2)
        self.assertEqual(report["byEventType"]["target_resolution_ambiguous"], 1)
        self.assertIn("Add canonical aliases", report["recommendedFixes"][0])

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

    def _insert_figure_storyline_contract_fixture(self, conn) -> None:
        conn.execute(
            "UPDATE stories SET title = ?, body = ? WHERE repo = ? AND issue_number = 3",
            (
                "[Story] 인물 스토리라인 등록·수정·삭제",
                "REQ-FIGURE-002",
                "loaring-story/loaring-product",
            ),
        )
        conn.execute(
            """
            INSERT INTO stories (
              repo, issue_number, title, state, url, labels_json,
              assignees_json, body, updated_at, synced_at
            )
            VALUES (
              'loaring-story/loaring-sotry', 370, '[Story] 인물 스토리라인 등록·수정·삭제',
              'open', 'https://github.com/loaring-story/loaring-sotry/issues/370',
              '[]', '[]', 'legacy', '2026-07-21T00:00:00Z', '2026-07-21T00:00:00Z'
            )
            """
        )
        endpoints = [
            {"id": "figure.storyline.create", "changePolicy": "contract-review-required"},
            {"id": "figure.storyline.update", "changePolicy": "contract-review-required"},
            {"id": "figure.storyline.delete", "changePolicy": "contract-review-required"},
        ]
        path = "docs/api/370-figure-storyline.api-spec.json"
        conn.execute(
            """
            INSERT INTO api_specs (
              repo, ref, path, domain, title, story_issue, requirement_ids_json,
              endpoints_json, lifecycle, updated_at
            )
            VALUES (
              'loaring-story/loaring-product', 'develop', ?, 'figure',
              '인물 스토리라인 등록·수정·삭제 API 명세', 3, ?, ?, 'accepted', ?
            )
            """,
            (path, json.dumps(["REQ-FIGURE-002"]), json.dumps(endpoints), now_iso()),
        )
        conn.execute(
            """
            INSERT INTO requirements (
              repo, ref, requirement_id, title, status, epic,
              story_issues_json, api_specs_json, updated_at
            )
            VALUES (
              'loaring-story/loaring-product', 'develop', 'REQ-FIGURE-002',
              '인물 스토리라인 등록·수정·삭제', 'accepted', 'Figure',
              '[3]', ?, ?
            )
            """,
            (json.dumps([path]), now_iso()),
        )
        conn.execute(
            """
            INSERT INTO product_snapshots (repo, ref, path, sha, content, fetched_at)
            VALUES ('loaring-story/loaring-product', 'develop', ?, 'sha', ?, ?)
            """,
            (path, json.dumps(self._figure_storyline_spec(), ensure_ascii=False), now_iso()),
        )

    def _figure_storyline_spec(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "meta": {"title": "인물 스토리라인 등록·수정·삭제 API 명세", "story": {"issue": 3}},
            "schemas": {
                "StorylineCreateRequest": {
                    "type": "object",
                    "required": ["content"],
                    "properties": {
                        "content": {"type": "string", "constraints": ["notBlank", "length:1..5000"]},
                        "imageUrl": {"type": "string", "constraints": ["url"]},
                    },
                },
                "StorylineResponse": {
                    "type": "object",
                    "required": ["id", "figureId", "content"],
                    "properties": {
                        "id": {"type": "number"},
                        "figureId": {"type": "number"},
                        "content": {"type": "string"},
                    },
                },
            },
            "endpoints": [
                {
                    "id": "figure.storyline.create",
                    "method": "POST",
                    "path": "/api/figures/{figureId}/storylines",
                    "request": {
                        "contentType": "application/json",
                        "pathParams": {"figureId": {"type": "number", "required": True}},
                        "queryParams": {},
                        "bodySchema": "StorylineCreateRequest",
                        "example": {"content": "text"},
                    },
                    "response": {"httpStatus": 201, "code": "0001", "bodySchema": "StorylineResponse"},
                    "errors": ["GLOBAL_002", "FIGURE_001"],
                    "consumerGuidance": {"schemaNames": ["StorylineCreateRequest"], "uiRules": ["등록 성공 시 목록을 갱신한다."]},
                },
                {
                    "id": "figure.storyline.update",
                    "method": "PATCH",
                    "path": "/api/figures/{figureId}/storylines/{storylineId}",
                    "request": {"bodySchema": "StorylineCreateRequest"},
                    "response": {"httpStatus": 200, "code": "0002", "bodySchema": "StorylineResponse"},
                    "errors": ["STORYLINE_001"],
                },
                {
                    "id": "figure.storyline.delete",
                    "method": "DELETE",
                    "path": "/api/figures/{figureId}/storylines/{storylineId}",
                    "request": {"bodySchema": None},
                    "response": {"httpStatus": 204, "code": "0003", "bodySchema": None},
                    "errors": ["STORYLINE_001"],
                },
            ],
            "errorCodes": [{"code": "GLOBAL_002", "httpStatus": 400}],
            "validationChecks": {"provider": ["validate content"], "consumer": ["refresh list"], "qa": ["create"]},
        }

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
