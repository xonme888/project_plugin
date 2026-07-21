"""MCP tool dispatch for LoaRing Product Ops."""

from __future__ import annotations

from typing import Any, Callable

from .github_project import sync_contract_readiness_options, update_project_fields
from .github_sync import find_cached_stories, get_story, sync_github, sync_project, sync_stories
from .migration import migration_dry_run
from .product_sync import (
    find_story,
    get_contract,
    infer_project_fields,
    sync_product,
    validate_contract_readiness,
)
from .workflow import (
    announce_doc_edit,
    apply_workflow_transition,
    contract_gap_report,
    create_api_contract_issue_comment,
    create_work_branch,
    detect_work_conflicts,
    link_pr_to_project,
    prepare_doc_edit,
    plan_story_work,
    prepare_branch,
    prepare_pr,
    sprint_report,
    validate_branch_name,
    validate_workflow,
)


JsonDict = dict[str, Any]


def tool_handlers() -> dict[str, Callable[[JsonDict], Any]]:
    return {
        "loaring_sync_product": lambda args: sync_product(repo=args.get("repo"), ref=args.get("ref")),
        "loaring_find_story": lambda args: find_story(
            args["query"],
            int(args.get("limit") or 10),
            repo=args.get("repo"),
            ref=args.get("ref"),
        ),
        "loaring_get_contract": lambda args: get_contract(
            story_issue=args.get("storyIssue"),
            requirement_id=args.get("requirementId"),
            repo=args.get("repo"),
            ref=args.get("ref"),
        ),
        "loaring_validate_contract_readiness": lambda args: validate_contract_readiness(
            story_issue=args.get("storyIssue"),
            requirement_id=args.get("requirementId"),
            repo=args.get("repo"),
            ref=args.get("ref"),
        ),
        "loaring_infer_project_fields": lambda args: infer_project_fields(
            story_issue=args.get("storyIssue"),
            requirement_id=args.get("requirementId"),
            repo=args.get("repo"),
            ref=args.get("ref"),
            number=args.get("projectNumber"),
        ),
        "loaring_sync_stories": lambda args: sync_stories(
            repo=args.get("repo"),
            label=args.get("label"),
            include_legacy=bool(args.get("includeLegacy")),
        ),
        "loaring_sync_project": lambda args: sync_project(
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_sync_github": lambda args: sync_github(
            repo=args.get("repo"),
            number=args.get("projectNumber"),
            include_legacy=bool(args.get("includeLegacy")),
        ),
        "loaring_get_story": lambda args: get_story(
            issue_number=int(args["issueNumber"]),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_find_cached_stories": lambda args: find_cached_stories(
            query=args["query"],
            limit=int(args.get("limit") or 10),
            repo=args.get("repo"),
        ),
        "loaring_migration_dry_run": lambda args: migration_dry_run(
            sync=bool(args.get("sync", True)),
            include_bodies=bool(args.get("includeBodies")),
            issue_numbers=args.get("issueNumbers"),
        ),
        "loaring_plan_story_work": lambda args: plan_story_work(
            story_issue=int(args["storyIssue"]),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_prepare_branch": lambda args: prepare_branch(
            story_issue=int(args["storyIssue"]),
            target=args["target"],
            slug=args.get("slug"),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_validate_workflow": lambda args: validate_workflow(
            repo=args.get("repo"),
            number=args.get("projectNumber"),
            sprint=args.get("sprint"),
            assignee=args.get("assignee"),
        ),
        "loaring_update_project_fields": lambda args: update_project_fields(
            story_issue=int(args["storyIssue"]),
            fields=args.get("fields"),
            apply=bool(args.get("apply")),
            confirm=bool(args.get("confirm")),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_sync_contract_readiness_options": lambda args: sync_contract_readiness_options(
            apply=bool(args.get("apply")),
            confirm=bool(args.get("confirm")),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_apply_workflow_transition": lambda args: apply_workflow_transition(
            story_issue=int(args["storyIssue"]),
            transition=args["transition"],
            apply=bool(args.get("apply")),
            confirm=bool(args.get("confirm")),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_create_work_branch": lambda args: create_work_branch(
            story_issue=int(args["storyIssue"]),
            target=args["target"],
            slug=args.get("slug"),
            cwd=args.get("cwd"),
            apply=bool(args.get("apply")),
            confirm=bool(args.get("confirm")),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_validate_branch_name": lambda args: validate_branch_name(
            story_issue=int(args["storyIssue"]),
            target=args["target"],
            branch=args.get("branch"),
            slug=args.get("slug"),
            cwd=args.get("cwd"),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_prepare_pr": lambda args: prepare_pr(
            story_issue=int(args["storyIssue"]),
            target=args["target"],
            branch=args.get("branch"),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_prepare_doc_edit": lambda args: prepare_doc_edit(
            story_issue=int(args["storyIssue"]),
            target=args.get("target") or "docs",
            files=args.get("files"),
            notify_users=args.get("notifyUsers"),
            slug=args.get("slug"),
            branch=args.get("branch"),
            pr_number=args.get("prNumber"),
            pr_url=args.get("prUrl"),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_announce_doc_edit": lambda args: announce_doc_edit(
            story_issue=int(args["storyIssue"]),
            target=args.get("target") or "docs",
            files=args.get("files"),
            notify_users=args.get("notifyUsers"),
            slug=args.get("slug"),
            branch=args.get("branch"),
            pr_number=args.get("prNumber"),
            pr_url=args.get("prUrl"),
            apply=bool(args.get("apply")),
            confirm=bool(args.get("confirm")),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_sprint_report": lambda args: sprint_report(
            repo=args.get("repo"),
            number=args.get("projectNumber"),
            sprint=args.get("sprint"),
            assignee=args.get("assignee"),
        ),
        "loaring_contract_gap_report": lambda args: contract_gap_report(
            repo=args.get("repo"),
            number=args.get("projectNumber"),
            sprint=args.get("sprint"),
            assignee=args.get("assignee"),
        ),
        "loaring_create_api_contract_issue_comment": lambda args: create_api_contract_issue_comment(
            story_issue=int(args["storyIssue"]),
            kind=args["kind"],
            question=args.get("question"),
            decision=args.get("decision"),
            apply=bool(args.get("apply")),
            confirm=bool(args.get("confirm")),
            repo=args.get("repo"),
            number=args.get("projectNumber"),
        ),
        "loaring_link_pr_to_project": lambda args: link_pr_to_project(
            pr_number=int(args["prNumber"]),
            story_issue=args.get("storyIssue"),
            body=args.get("body"),
            apply=bool(args.get("apply")),
            confirm=bool(args.get("confirm")),
            repo=args.get("repo"),
            pr_repo=args.get("prRepo"),
            number=args.get("projectNumber"),
        ),
        "loaring_detect_work_conflicts": lambda args: detect_work_conflicts(
            story_issue=int(args["storyIssue"]),
            target=args.get("target"),
            files=args.get("files"),
            repo=args.get("repo"),
            pr_repos=args.get("prRepos"),
        ),
    }


def available_tool_names() -> set[str]:
    return set(tool_handlers())


def call_tool(name: str, arguments: JsonDict) -> Any:
    handlers = tool_handlers()
    if name not in handlers:
        raise ValueError(f"Unknown tool: {name}")
    return handlers[name](arguments)
