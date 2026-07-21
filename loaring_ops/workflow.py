"""Workflow planning helpers for cached LoaRing product data."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from .config import project_number, story_repo_name
from .db import connect, init_db
from .github_client import gh_api, gh_api_post
from .github_sync import decode_project, decode_story
from .github_project import STATUS_TRANSITIONS, current_project_iteration, require_confirm, update_project_fields
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


def create_work_branch(
    story_issue: int,
    target: str,
    slug: str | None = None,
    repo: str | None = None,
    number: int | None = None,
    cwd: str | None = None,
    apply: bool = False,  # noqa: A002 - MCP argument name
    confirm: bool = False,
) -> dict[str, Any]:
    plan = prepare_branch(story_issue, target, slug=slug, repo=repo, number=number)
    result: dict[str, Any] = {
        **plan,
        "cwd": cwd,
        "apply": apply,
        "confirmed": confirm,
    }
    if not apply:
        result["status"] = "planned"
        result["message"] = "Set apply=true and confirm=true to run git switch -c in the selected repo."
        return result
    require_confirm(confirm)
    command = ["git", "switch", "-c", plan["branch"]]
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    result["command"] = " ".join(command)
    result["stdout"] = completed.stdout.strip()
    result["stderr"] = completed.stderr.strip()
    result["returnCode"] = completed.returncode
    result["status"] = "created" if completed.returncode == 0 else "failed"
    if completed.returncode != 0:
        raise RuntimeError(result["stderr"] or result["stdout"] or "git switch failed")
    return result


def validate_branch_name(
    story_issue: int,
    target: str,
    branch: str | None = None,
    slug: str | None = None,
    repo: str | None = None,
    number: int | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    plan = prepare_branch(story_issue, target, slug=slug, repo=repo, number=number)
    actual = branch or current_branch(cwd)
    pattern = branch_pattern(story_issue, normalize_target(target))
    return {
        "storyIssue": story_issue,
        "target": plan["target"],
        "actualBranch": actual,
        "expectedBranch": plan["branch"],
        "pattern": pattern.pattern,
        "valid": bool(actual and pattern.fullmatch(actual)),
        "message": "Branch name matches LoaRing workflow rules."
        if actual and pattern.fullmatch(actual)
        else "Branch name does not match the expected Story/target rule.",
    }


def apply_workflow_transition(
    story_issue: int,
    transition: str,
    repo: str | None = None,
    number: int | None = None,
    apply: bool = False,  # noqa: A002 - MCP argument name
    confirm: bool = False,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    story, project = cached_story_and_project(story_issue, selected_repo, selected_project)
    fields = (project or {}).get("fields", {})
    inference = infer_project_fields(story_issue=story_issue, repo=selected_repo, number=selected_project)
    merged = {**inference["recommendedFields"], **fields}
    normalized = transition.strip().lower()
    if normalized not in STATUS_TRANSITIONS:
        raise ValueError(f"Unsupported workflow transition: {transition}")
    target_status = STATUS_TRANSITIONS[normalized]
    blockers = transition_blockers(normalized, merged)
    result: dict[str, Any] = {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "storyIssue": story_issue,
        "transition": normalized,
        "targetStatus": target_status,
        "apply": apply,
        "confirmed": confirm,
        "story": story_summary(story),
        "fields": fields,
        "effectiveFields": merged,
        "blockers": blockers,
    }
    if blockers:
        result["status"] = "blocked"
        return result
    if not apply:
        result["status"] = "planned"
        result["changes"] = [{"field": "Status", "current": fields.get("Status"), "desired": target_status}]
        result["message"] = "Set apply=true and confirm=true to write the Status field."
        return result
    require_confirm(confirm)
    applied = update_project_fields(
        story_issue=story_issue,
        fields={"Status": target_status},
        apply=True,
        confirm=True,
        repo=selected_repo,
        number=selected_project,
    )
    result["status"] = "applied"
    result["applied"] = applied
    return result


def prepare_pr(
    story_issue: int,
    target: str,
    repo: str | None = None,
    number: int | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    story, project = cached_story_and_project(story_issue, selected_repo, selected_project)
    fields = (project or {}).get("fields", {})
    inference = infer_project_fields(story_issue=story_issue, repo=selected_repo, number=selected_project)
    readiness = fields.get("Contract Readiness") or inference["recommendedFields"]["Contract Readiness"]
    implementation_target = fields.get("Implementation Target") or inference["recommendedFields"]["Implementation Target"]
    normalized_target = normalize_target(target)
    blockers = implementation_blockers(normalized_target, {
        "Contract Required": fields.get("Contract Required") or inference["recommendedFields"]["Contract Required"],
        "Contract Readiness": readiness,
        "Implementation Target": implementation_target,
    })
    title_target = {
        "backend": "Backend",
        "frontend": "Frontend",
        "contract": "Contract",
        "product": "Product",
    }.get(normalized_target, normalized_target.title())
    story_title = (story or {}).get("title") or f"Story #{story_issue}"
    title = f"{title_target}: {story_title} (#{story_issue})"
    body = "\n".join(
        [
            f"Related #{story_issue}",
            "",
            "## Scope",
            f"- Target: {title_target}",
            f"- Contract Readiness: {readiness}",
            f"- Implementation Target: {implementation_target}",
            "",
            "## Checks",
            "- [ ] Story acceptance criteria reviewed",
            "- [ ] Contract impact checked",
            "- [ ] QA notes updated if needed",
        ]
    )
    return {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "storyIssue": story_issue,
        "target": normalized_target,
        "branch": branch,
        "title": title,
        "body": body,
        "blocked": bool(blockers),
        "blockers": blockers,
        "story": story_summary(story),
        "fields": fields,
        "inference": inference,
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
    assignee: str | None = None,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    resolved_sprint = sprint
    current_sprint = None
    if resolved_sprint is None:
        current_sprint = current_project_iteration(selected_repo, selected_project)
        resolved_sprint = (current_sprint or {}).get("title")
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
        if resolved_sprint and fields.get("Sprint") != resolved_sprint:
            continue
        if assignee and assignee not in set(story.get("assignees") or []):
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
        "sprint": resolved_sprint,
        "currentSprint": current_sprint,
        "assignee": assignee,
        "storyCount": len(stories),
        "findingCount": len(findings),
        "findings": findings,
        "stories": stories,
    }


def sprint_report(
    repo: str | None = None,
    number: int | None = None,
    sprint: str | None = None,
    assignee: str | None = None,
) -> dict[str, Any]:
    validation = validate_workflow(repo=repo, number=number, sprint=sprint, assignee=assignee)
    summary: dict[str, dict[str, int]] = {
        "byStatus": {},
        "byReadiness": {},
        "byTarget": {},
    }
    blockers: list[dict[str, Any]] = []
    for story in validation["stories"]:
        fields = story["fields"]
        bump(summary["byStatus"], str(fields.get("Status") or "Unassigned"))
        bump(summary["byReadiness"], str(fields.get("Contract Readiness") or "Unassigned"))
        bump(summary["byTarget"], str(fields.get("Implementation Target") or "Unassigned"))
        if story["findings"]:
            blockers.append(
                {
                    "issueNumber": story["issueNumber"],
                    "title": story["title"],
                    "findings": story["findings"],
                }
            )
    return {
        "repo": validation["repo"],
        "projectNumber": validation["projectNumber"],
        "sprint": validation["sprint"],
        "currentSprint": validation["currentSprint"],
        "assignee": validation["assignee"],
        "storyCount": validation["storyCount"],
        "summary": summary,
        "blockerCount": len(blockers),
        "blockers": blockers,
    }


def contract_gap_report(
    repo: str | None = None,
    number: int | None = None,
    sprint: str | None = None,
    assignee: str | None = None,
) -> dict[str, Any]:
    validation = validate_workflow(repo=repo, number=number, sprint=sprint, assignee=assignee)
    gaps: list[dict[str, Any]] = []
    for story in validation["stories"]:
        fields = story["fields"]
        required = fields.get("Contract Required") or story["recommendedFields"].get("Contract Required")
        readiness = fields.get("Contract Readiness") or story["recommendedFields"].get("Contract Readiness")
        if required == "Yes" and readiness in {"Missing", "Draft", "Blocked"}:
            gaps.append(
                {
                    "issueNumber": story["issueNumber"],
                    "title": story["title"],
                    "url": story["url"],
                    "contractReadiness": readiness,
                    "implementationTarget": fields.get("Implementation Target")
                    or story["recommendedFields"].get("Implementation Target"),
                    "recommendedFields": story["recommendedFields"],
                }
            )
    return {
        "repo": validation["repo"],
        "projectNumber": validation["projectNumber"],
        "sprint": validation["sprint"],
        "currentSprint": validation["currentSprint"],
        "assignee": validation["assignee"],
        "gapCount": len(gaps),
        "gaps": gaps,
    }


def create_api_contract_issue_comment(
    story_issue: int,
    kind: str,
    question: str | None = None,
    decision: str | None = None,
    repo: str | None = None,
    number: int | None = None,
    apply: bool = False,  # noqa: A002 - MCP argument name
    confirm: bool = False,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    story, project = cached_story_and_project(story_issue, selected_repo, selected_project)
    normalized_kind = kind.strip().lower()
    if normalized_kind not in {"question", "decision"}:
        raise ValueError("kind must be question or decision")
    heading = "[계약 질문]" if normalized_kind == "question" else "[계약 결정]"
    content = question if normalized_kind == "question" else decision
    if not content:
        content = "TODO: API 요청/응답/에러/권한/검증 기준을 구체적으로 적는다."
    body = "\n".join(
        [
            heading,
            "",
            f"- Story: #{story_issue}",
            f"- 제목: {(story or {}).get('title') or ''}",
            f"- Contract Readiness: {((project or {}).get('fields') or {}).get('Contract Readiness') or ''}",
            "",
            content,
        ]
    )
    result: dict[str, Any] = {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "storyIssue": story_issue,
        "kind": normalized_kind,
        "body": body,
        "apply": apply,
        "confirmed": confirm,
        "story": story_summary(story),
        "projectFields": (project or {}).get("fields", {}),
    }
    if not apply:
        result["status"] = "planned"
        result["message"] = "Set apply=true and confirm=true to post this Issue comment."
        return result
    require_confirm(confirm)
    posted = gh_api_post(f"repos/{selected_repo}/issues/{story_issue}/comments", {"body": body})
    result["status"] = "posted"
    result["comment"] = {
        "id": posted.get("id"),
        "url": posted.get("html_url"),
    }
    return result


def link_pr_to_project(
    pr_number: int,
    story_issue: int | None = None,
    repo: str | None = None,
    number: int | None = None,
    body: str | None = None,
    apply: bool = False,  # noqa: A002 - MCP argument name
    confirm: bool = False,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    pr_payload: dict[str, Any] | None = None
    pr_body = body
    if pr_body is None:
        pr_payload = gh_api(f"repos/{selected_repo}/pulls/{pr_number}")
        pr_body = pr_payload.get("body") or ""
    detected = detect_related_story(pr_body)
    selected_story = story_issue or detected
    missing_related = selected_story is None or f"#{selected_story}" not in pr_body
    result: dict[str, Any] = {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "prNumber": pr_number,
        "storyIssue": selected_story,
        "detectedStoryIssue": detected,
        "hasRelatedReference": not missing_related,
        "apply": apply,
        "confirmed": confirm,
        "pr": None if pr_payload is None else {
            "title": pr_payload.get("title"),
            "state": pr_payload.get("state"),
            "url": pr_payload.get("html_url"),
        },
    }
    if missing_related:
        result["status"] = "blocked"
        result["blockers"] = ["PR body is missing a Related #<story> reference."]
        return result
    if not apply:
        result["status"] = "planned"
        result["message"] = "Set apply=true and confirm=true to move the linked Story to In Request."
        result["changes"] = [{"storyIssue": selected_story, "field": "Status", "desired": "In Request"}]
        return result
    require_confirm(confirm)
    assert selected_story is not None
    transition = apply_workflow_transition(
        story_issue=selected_story,
        transition="request-review",
        repo=selected_repo,
        number=selected_project,
        apply=True,
        confirm=True,
    )
    result["status"] = "applied"
    result["transition"] = transition
    return result


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


def current_branch(cwd: str | None = None) -> str | None:
    completed = subprocess.run(["git", "branch", "--show-current"], cwd=cwd, capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def branch_pattern(story_issue: int, target: str) -> re.Pattern[str]:
    prefix = TARGET_PREFIXES[target]
    suffix = r"-contract" if target == "contract" else ""
    return re.compile(rf"{re.escape(prefix)}/{story_issue}-[a-z0-9]+(?:-[a-z0-9]+)*{suffix}")


def transition_blockers(transition: str, fields: dict[str, Any]) -> list[str]:
    if transition in {"start-backend", "start-frontend"}:
        target = "backend" if transition == "start-backend" else "frontend" if transition == "start-frontend" else "backend"
        blockers = implementation_blockers(target, fields)
        if blockers:
            return blockers
    if transition == "request-review" and fields.get("Contract Required") == "Yes":
        readiness = fields.get("Contract Readiness")
        if readiness in {"Missing", "Draft", "Blocked"}:
            return [f"Contract Required=Yes but Contract Readiness is {readiness}."]
    if transition in {"qa-pass", "complete"}:
        required = fields.get("Contract Required")
        readiness = fields.get("Contract Readiness")
        target = fields.get("Implementation Target")
        if required == "Yes" and not completion_readiness_ok(target, readiness):
            return [f"Cannot complete {target or 'Story'} while Contract Readiness is {readiness}."]
    return []


def implementation_blockers(target: str, fields: dict[str, Any]) -> list[str]:
    required = fields.get("Contract Required")
    readiness = fields.get("Contract Readiness")
    implementation_target = fields.get("Implementation Target")
    if required != "Yes":
        return []
    if readiness in {"Missing", "Draft", "Blocked"}:
        return [f"Contract Required=Yes but Contract Readiness is {readiness}."]
    if target == "backend" and readiness not in {"Backend Ready", "Ready"}:
        return [f"Backend work requires Backend Ready or Ready, got {readiness}."]
    if target == "frontend" and readiness not in {"Frontend Ready", "Ready"}:
        return [f"Frontend work requires Frontend Ready or Ready, got {readiness}."]
    if target == "backend" and implementation_target not in {"Backend", "Backend+Frontend"}:
        return [f"Implementation Target does not include Backend: {implementation_target}."]
    if target == "frontend" and implementation_target not in {"Frontend", "Backend+Frontend"}:
        return [f"Implementation Target does not include Frontend: {implementation_target}."]
    return []


def completion_readiness_ok(target: str | None, readiness: str | None) -> bool:
    if target == "Backend":
        return readiness in {"Backend Ready", "Ready"}
    if target == "Frontend":
        return readiness in {"Frontend Ready", "Ready"}
    if target == "Backend+Frontend":
        return readiness == "Ready"
    return readiness not in {"Missing", "Draft", "Blocked"}


def bump(values: dict[str, int], key: str) -> None:
    values[key] = values.get(key, 0) + 1


def detect_related_story(body: str) -> int | None:
    patterns = [
        r"Related\s+#(\d+)",
        r"Relates\s+to\s+#(\d+)",
        r"Closes\s+#(\d+)",
        r"Fixes\s+#(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


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
