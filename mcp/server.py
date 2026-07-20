#!/usr/bin/env python3
"""Minimal stdio MCP server for LoaRing Product Ops."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loaring_ops.product_sync import (  # noqa: E402
    find_story,
    get_contract,
    infer_project_fields,
    sync_product,
    validate_contract_readiness,
)
from loaring_ops.github_sync import (  # noqa: E402
    find_cached_stories,
    get_story,
    sync_github,
    sync_project,
    sync_stories,
)
from loaring_ops.github_project import (  # noqa: E402
    sync_contract_readiness_options,
    update_project_fields,
)
from loaring_ops.migration import migration_dry_run  # noqa: E402
from loaring_ops.workflow import (  # noqa: E402
    apply_workflow_transition,
    contract_gap_report,
    create_api_contract_issue_comment,
    create_work_branch,
    link_pr_to_project,
    plan_story_work,
    prepare_pr,
    prepare_branch,
    sprint_report,
    validate_branch_name,
    validate_workflow,
)


JsonDict = dict[str, Any]


TOOLS: dict[str, dict[str, Any]] = {
    "loaring_sync_product": {
        "description": "Sync read-only loaring-product docs into the local sqlite cache.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "ref": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_find_story": {
        "description": "Find cached LoaRing requirements, story-map rows, and API specs by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    "loaring_get_contract": {
        "description": "Get cached API contract metadata linked to a Story issue or requirement id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "requirementId": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_validate_contract_readiness": {
        "description": "Check whether a Story or requirement has linked full API contract metadata ready for implementation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "requirementId": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_infer_project_fields": {
        "description": "Infer Contract Required, Contract Readiness, and Implementation Target from cached product docs and Story metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "requirementId": {"type": "string"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_sync_stories": {
        "description": "Sync read-only GitHub Story issues from the Story repo into the local sqlite cache.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "label": {"type": "string"},
                "includeLegacy": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_sync_project": {
        "description": "Sync read-only GitHub Project field values for Story issues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_sync_github": {
        "description": "Sync read-only GitHub Story issues and Project field values from the Story repo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "includeLegacy": {"type": "boolean"},
                "projectNumber": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_get_story": {
        "description": "Get a cached Story issue with cached GitHub Project field values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issueNumber": {"type": "integer"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["issueNumber"],
            "additionalProperties": False,
        },
    },
    "loaring_find_cached_stories": {
        "description": "Search cached GitHub Story issue title/body text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    "loaring_migration_dry_run": {
        "description": "Build a read-only migration plan from legacy Story issues into loaring-product.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sync": {"type": "boolean"},
                "includeBodies": {"type": "boolean"},
                "issueNumbers": {
                    "type": "array",
                    "items": {"type": "integer"},
                },
            },
            "additionalProperties": False,
        },
    },
    "loaring_plan_story_work": {
        "description": "Plan the next workflow actions and branch suggestions for one cached Story.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue"],
            "additionalProperties": False,
        },
    },
    "loaring_prepare_branch": {
        "description": "Generate the expected branch name and git commands for a Story target.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "target": {"type": "string", "description": "One of product, contract, backend, frontend, fix, docs, chore."},
                "slug": {"type": "string"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue", "target"],
            "additionalProperties": False,
        },
    },
    "loaring_validate_workflow": {
        "description": "Validate cached Project Stories for missing fields, contract/status mismatches, and workflow risks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
                "sprint": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_update_project_fields": {
        "description": "Plan or apply inferred Story field updates to GitHub Project #7. Writes require apply=true and confirm=true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "fields": {"type": "object", "additionalProperties": {"type": "string"}},
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue"],
            "additionalProperties": False,
        },
    },
    "loaring_sync_contract_readiness_options": {
        "description": "Check or rewrite the Project Contract Readiness options to the LoaRing standard values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_apply_workflow_transition": {
        "description": "Plan or apply a Story workflow Status transition with contract-readiness gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "transition": {
                    "type": "string",
                    "description": "start-contract, start-product, start-backend, start-frontend, request-review, qa-pass, complete, or block.",
                },
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue", "transition"],
            "additionalProperties": False,
        },
    },
    "loaring_create_work_branch": {
        "description": "Plan or run git switch -c for a Story target branch in the current implementation repo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "target": {"type": "string", "description": "product, contract, backend, frontend, fix, docs, or chore."},
                "slug": {"type": "string"},
                "cwd": {"type": "string"},
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue", "target"],
            "additionalProperties": False,
        },
    },
    "loaring_validate_branch_name": {
        "description": "Validate that the current or provided branch name matches the Story/target branch rule.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "target": {"type": "string", "description": "product, contract, backend, frontend, fix, docs, or chore."},
                "branch": {"type": "string"},
                "slug": {"type": "string"},
                "cwd": {"type": "string"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue", "target"],
            "additionalProperties": False,
        },
    },
    "loaring_prepare_pr": {
        "description": "Create a PR title/body draft from Story, target, contract readiness, and implementation target.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "target": {"type": "string", "description": "product, contract, backend, frontend, fix, docs, or chore."},
                "branch": {"type": "string"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue", "target"],
            "additionalProperties": False,
        },
    },
    "loaring_sprint_report": {
        "description": "Summarize Sprint Stories by Status, Contract Readiness, Implementation Target, and blockers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
                "sprint": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_contract_gap_report": {
        "description": "List Stories whose API contract is required but Missing, Draft, or Blocked.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
                "sprint": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "loaring_create_api_contract_issue_comment": {
        "description": "Generate or post a standardized [계약 질문] or [계약 결정] Issue comment body.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "kind": {"type": "string", "description": "question or decision."},
                "question": {"type": "string"},
                "decision": {"type": "string"},
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue", "kind"],
            "additionalProperties": False,
        },
    },
    "loaring_link_pr_to_project": {
        "description": "Check PR Story linkage and optionally move the linked Story to In Request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prNumber": {"type": "integer"},
                "storyIssue": {"type": "integer"},
                "body": {"type": "string"},
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "PR and Story repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["prNumber"],
            "additionalProperties": False,
        },
    },
}


def send(payload: JsonDict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def result(request_id: Any, value: Any) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": value})


def error(request_id: Any, code: int, message: str, data: Any | None = None) -> None:
    payload: JsonDict = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if data is not None:
        payload["error"]["data"] = data
    send(payload)


def text_content(value: Any) -> JsonDict:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(value, ensure_ascii=False, indent=2),
            }
        ]
    }


def handle_initialize(params: JsonDict) -> JsonDict:
    return {
        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
        "serverInfo": {"name": "loaring-product-ops", "version": "0.1.0"},
        "capabilities": {"tools": {}},
    }


def handle_tools_list(_: JsonDict) -> JsonDict:
    return {
        "tools": [
            {"name": name, **definition}
            for name, definition in TOOLS.items()
        ]
    }


def call_tool(name: str, arguments: JsonDict) -> Any:
    handlers: dict[str, Callable[[JsonDict], Any]] = {
        "loaring_sync_product": lambda args: sync_product(repo=args.get("repo"), ref=args.get("ref")),
        "loaring_find_story": lambda args: find_story(args["query"], int(args.get("limit") or 10)),
        "loaring_get_contract": lambda args: get_contract(
            story_issue=args.get("storyIssue"),
            requirement_id=args.get("requirementId"),
        ),
        "loaring_validate_contract_readiness": lambda args: validate_contract_readiness(
            story_issue=args.get("storyIssue"),
            requirement_id=args.get("requirementId"),
        ),
        "loaring_infer_project_fields": lambda args: infer_project_fields(
            story_issue=args.get("storyIssue"),
            requirement_id=args.get("requirementId"),
            repo=args.get("repo"),
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
        "loaring_sprint_report": lambda args: sprint_report(
            repo=args.get("repo"),
            number=args.get("projectNumber"),
            sprint=args.get("sprint"),
        ),
        "loaring_contract_gap_report": lambda args: contract_gap_report(
            repo=args.get("repo"),
            number=args.get("projectNumber"),
            sprint=args.get("sprint"),
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
            number=args.get("projectNumber"),
        ),
    }
    if name not in handlers:
        raise ValueError(f"Unknown tool: {name}")
    return handlers[name](arguments)


def handle_tools_call(params: JsonDict) -> JsonDict:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str):
        raise ValueError("tools/call requires a tool name")
    if not isinstance(arguments, dict):
        raise ValueError("tools/call arguments must be an object")
    return text_content(call_tool(name, arguments))


def handle_request(message: JsonDict) -> None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    if not isinstance(params, dict):
        error(request_id, -32602, "params must be an object")
        return

    try:
        if method == "initialize":
            result(request_id, handle_initialize(params))
        elif method == "tools/list":
            result(request_id, handle_tools_list(params))
        elif method == "tools/call":
            result(request_id, handle_tools_call(params))
        elif method in {"notifications/initialized", "initialized"}:
            return
        else:
            error(request_id, -32601, f"Method not found: {method}")
    except Exception as exc:  # noqa: BLE001 - MCP error boundary
        error(request_id, -32000, str(exc), traceback.format_exc())


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            error(None, -32700, f"Parse error: {exc}")
            continue
        if isinstance(message, dict):
            handle_request(message)
        else:
            error(None, -32600, "Invalid request")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
