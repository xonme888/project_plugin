"""Workflow planning helpers for cached LoaRing product data."""

from __future__ import annotations

import json
import re
from typing import Any

from .config import project_number, story_repo_name
from .db import connect, init_db
from .github_sync import decode_project, decode_story
from .product_sync import get_contract, infer_project_fields


TARGET_PREFIXES = {
    "product": "docs",
    "contract": "docs",
    "backend": "be",
    "frontend": "fe",
    "fix": "fix",
    "docs": "docs",
    "chore": "chore",
}


def prepare_branch(
    story_issue: int,
    target: str,
    slug: str | None = None,
    repo: str | None = None,
    number: int | None = None,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    story, project = cached_story_and_project(story_issue, selected_repo, selected_project)
    normalized_target = normalize_target(target)
    branch_slug = normalize_slug(slug or infer_slug(story, project, story_issue))
    branch = branch_name(story_issue, normalized_target, branch_slug)
    return {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "storyIssue": story_issue,
        "target": normalized_target,
        "branch": branch,
        "commands": {
            "create": f"git switch -c {branch}",
            "push": f"git push -u origin {branch}",
        },
        "source": {
            "story": story_summary(story),
            "projectFields": (project or {}).get("fields", {}),
        },
    }


def plan_story_work(story_issue: int, repo: str | None = None, number: int | None = None) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    story, project = cached_story_and_project(story_issue, selected_repo, selected_project)
    field_inference = infer_project_fields(story_issue=story_issue, repo=selected_repo, number=selected_project)
    fields = (project or {}).get("fields", {})
    contract = get_contract(story_issue=story_issue)
    target = fields.get("Implementation Target") or field_inference["recommendedFields"]["Implementation Target"]
    readiness = fields.get("Contract Readiness") or field_inference["recommendedFields"]["Contract Readiness"]
    status = fields.get("Status")

    actions = next_actions(status, readiness, target, bool(contract["apiSpecs"]))
    branches = branch_suggestions(story_issue, story, target, readiness)
    return {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "storyIssue": story_issue,
        "story": story_summary(story),
        "projectFields": fields,
        "contract": {
            "requirements": contract["requirements"],
            "apiSpecs": contract["apiSpecs"],
        },
        "fieldInference": field_inference,
        "nextActions": actions,
        "branchSuggestions": branches,
    }


def validate_workflow(
    repo: str | None = None,
    number: int | None = None,
    sprint: str | None = None,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    conn = connect()
    init_db(conn)
    rows = conn.execute(
        """
        SELECT stories.*, project_items.fields_json, project_items.item_id
        FROM stories
        LEFT JOIN project_items
          ON project_items.repo = stories.repo
         AND project_items.issue_number = stories.issue_number
         AND project_items.project_number = ?
        WHERE stories.repo = ?
        ORDER BY stories.issue_number
        """,
        (selected_project, selected_repo),
    ).fetchall()

    findings: list[dict[str, Any]] = []
    stories: list[dict[str, Any]] = []
    for row in rows:
        story = decode_story(row)
        fields = json.loads(row["fields_json"] or "{}")
        if sprint and fields.get("Sprint") != sprint:
            continue
        issue_number = int(row["issue_number"])
        inference = infer_project_fields(story_issue=issue_number, repo=selected_repo, number=selected_project)
        story_findings = workflow_findings(issue_number, fields, inference)
        findings.extend(story_findings)
        stories.append(
            {
                "issueNumber": issue_number,
                "title": story["title"],
                "url": story["url"],
                "fields": fields,
                "recommendedFields": inference["recommendedFields"],
                "findings": story_findings,
            }
        )

    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["issueNumber"]))
    return {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "sprint": sprint,
        "storyCount": len(stories),
        "findingCount": len(findings),
        "findings": findings,
        "stories": stories,
    }


def cached_story_and_project(
    story_issue: int,
    repo: str,
    selected_project: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    conn = connect()
    init_db(conn)
    story_row = conn.execute(
        "SELECT * FROM stories WHERE repo = ? AND issue_number = ?",
        (repo, story_issue),
    ).fetchone()
    project_row = conn.execute(
        "SELECT * FROM project_items WHERE repo = ? AND project_number = ? AND issue_number = ?",
        (repo, selected_project, story_issue),
    ).fetchone()
    return decode_story(story_row), decode_project(project_row)


def next_actions(status: str | None, readiness: str, target: str, has_spec: bool) -> list[str]:
    actions: list[str] = []
    if readiness == "Missing":
        actions.append("Run api-contract for a contract brief or full api-spec decision before backend/frontend implementation.")
    elif readiness == "Draft":
        actions.append("Review and accept the API contract before implementation branches start.")
    elif readiness == "Backend Ready":
        actions.append("Backend implementation can start; frontend implementation still needs consumer-facing contract evidence.")
    elif readiness == "Frontend Ready":
        actions.append("Frontend implementation can start; backend implementation still needs provider-facing contract evidence.")
    elif readiness == "Ready":
        actions.append("Backend and frontend implementation can start from the accepted product API contract.")
    elif readiness == "Not Required":
        actions.append("No API contract gate is required; proceed with the product or QA task.")

    if target == "Backend+Frontend":
        if readiness == "Ready":
            actions.append("Prepare backend and frontend branches from the Story number.")
        elif readiness == "Backend Ready":
            actions.append("Prepare the backend branch and keep frontend blocked until Frontend Ready or Ready.")
        elif readiness == "Frontend Ready":
            actions.append("Prepare the frontend branch and keep backend blocked until Backend Ready or Ready.")
        elif has_spec:
            actions.append("Keep implementation limited to the side that is readiness-approved.")
        else:
            actions.append("Keep backend/frontend implementation blocked until the contract is linked.")
    elif target == "Backend":
        actions.append("Prepare a backend branch.")
    elif target == "Frontend":
        actions.append("Prepare a frontend branch.")
    elif target == "Product":
        actions.append("Prepare a product docs branch or refine the Story/API decision.")
    elif target == "QA":
        actions.append("Prepare QA verification notes from Story done criteria.")

    if status in {None, "", "Backlog", "Todo"}:
        actions.append("Move Status to In Progress when the first product, backend, or frontend branch starts.")
    elif status == "In Progress":
        actions.append("Move Status to In Request when implementation PRs are ready for review.")
    elif status == "In Request":
        actions.append("Move Status to Done only after review and QA pass.")
    return actions


def branch_suggestions(
    story_issue: int,
    story: dict[str, Any] | None,
    target: str,
    readiness: str,
) -> list[dict[str, str]]:
    slug = normalize_slug(infer_slug(story, None, story_issue))
    suggestions: list[dict[str, str]] = []
    if readiness in {"Missing", "Draft", "Blocked"}:
        suggestions.append({"target": "contract", "branch": branch_name(story_issue, "contract", slug)})
    if target in {"Backend", "Backend+Frontend"} and readiness in {"Backend Ready", "Ready"}:
        suggestions.append({"target": "backend", "branch": branch_name(story_issue, "backend", slug)})
    if target in {"Frontend", "Backend+Frontend"} and readiness in {"Frontend Ready", "Ready"}:
        suggestions.append({"target": "frontend", "branch": branch_name(story_issue, "frontend", slug)})
    if target == "Product":
        suggestions.append({"target": "product", "branch": branch_name(story_issue, "product", slug)})
    return suggestions


def workflow_findings(
    issue_number: int,
    fields: dict[str, Any],
    inference: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    required = ["Status", "Epic", "Sprint", "Story Point", "Contract Required", "Contract Readiness", "Implementation Target"]
    for field in required:
        if fields.get(field) in {None, ""}:
            findings.append(finding(issue_number, "warning", field, "missing-field", f"{field} is empty."))

    for mismatch in inference["mismatches"]:
        findings.append(
            finding(
                issue_number,
                "warning",
                mismatch["field"],
                "field-mismatch",
                f"{mismatch['field']} is {mismatch['current']}; recommended {mismatch['recommended']}.",
            )
        )

    status = fields.get("Status")
    readiness = fields.get("Contract Readiness")
    target = fields.get("Implementation Target")
    if status in {"In Progress", "In Request", "Done"} and readiness in {"Missing", "Draft", "Blocked"} and target != "Product":
        findings.append(
            finding(
                issue_number,
                "error",
                "Contract Readiness",
                "implementation-without-contract",
                "Implementation status is active but API contract is not side-ready.",
            )
        )
    if status == "Done" and readiness != "Ready" and fields.get("Contract Required") == "Yes":
        findings.append(
            finding(
                issue_number,
                "error",
                "Status",
                "done-before-contract-ready",
                "Story is Done while required contract is not Ready.",
            )
        )
    return findings


def finding(issue_number: int, severity: str, field: str, code: str, message: str) -> dict[str, Any]:
    return {
        "issueNumber": issue_number,
        "severity": severity,
        "field": field,
        "code": code,
        "message": message,
    }


def normalize_target(target: str) -> str:
    normalized = target.strip().lower()
    aliases = {
        "be": "backend",
        "fe": "frontend",
        "product-contract": "contract",
        "api-contract": "contract",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in TARGET_PREFIXES:
        raise ValueError(f"Unsupported target: {target}")
    return normalized


def branch_name(story_issue: int, target: str, slug: str) -> str:
    prefix = TARGET_PREFIXES[target]
    suffix = f"{slug}-contract" if target == "contract" and not slug.endswith("contract") else slug
    return f"{prefix}/{story_issue}-{suffix}"


def infer_slug(story: dict[str, Any] | None, project: dict[str, Any] | None, story_issue: int) -> str:
    text = f"{(story or {}).get('title') or ''}\n{((project or {}).get('fields') or {}).get('Epic') or ''}"
    keyword_slugs = [
        (["회원가입", "동의"], "signup-consent"),
        (["선호", "인물"], "preferred-figures"),
        (["스토리라인", "등록"], "figure-storyline"),
        (["공개", "여부"], "storyline-visibility"),
        (["대표", "사건"], "figure-events"),
        (["대화", "페이지"], "storyline-chat"),
        (["인물", "조회"], "figure-search"),
    ]
    for keywords, slug in keyword_slugs:
        if all(keyword in text for keyword in keywords):
            return slug
    ascii_words = re.findall(r"[A-Za-z0-9]+", text.lower())
    if ascii_words:
        return "-".join(ascii_words[:5])
    return f"story-{story_issue}"


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "story"


def story_summary(story: dict[str, Any] | None) -> dict[str, Any] | None:
    if story is None:
        return None
    return {
        "issueNumber": story.get("issue_number"),
        "title": story.get("title"),
        "state": story.get("state"),
        "url": story.get("url"),
        "labels": story.get("labels"),
        "assignees": story.get("assignees"),
    }
