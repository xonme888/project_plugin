"""MCP tool schemas for LoaRing Product Ops."""

from __future__ import annotations

from typing import Any


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
                "repo": {"type": "string", "description": "Product docs repo. Defaults to loaring-story/loaring-product."},
                "ref": {"type": "string", "description": "Product docs ref. Defaults to develop."},
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
                "repo": {"type": "string", "description": "Product docs repo. Defaults to loaring-story/loaring-product."},
                "ref": {"type": "string", "description": "Product docs ref. Defaults to develop."},
            },
            "additionalProperties": False,
        },
    },
    "loaring_resolve_contract_target": {
        "description": "Resolve a Story/query/requirement/api-spec hint to the canonical loaring-product contract target, including legacy Story mappings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "storyIssue": {"type": "integer"},
                "requirementId": {"type": "string"},
                "apiSpecPath": {"type": "string"},
                "repo": {"type": "string", "description": "Product docs repo. Defaults to loaring-story/loaring-product."},
                "ref": {"type": "string", "description": "Product docs ref. Defaults to develop."},
            },
            "additionalProperties": False,
        },
    },
    "loaring_get_api_spec": {
        "description": "Get cached full api-spec endpoint, request/response schema, error, validation, and consumer guidance summaries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "storyIssue": {"type": "integer"},
                "requirementId": {"type": "string"},
                "endpointId": {"type": "string"},
                "repo": {"type": "string", "description": "Product docs repo. Defaults to loaring-story/loaring-product."},
                "ref": {"type": "string", "description": "Product docs ref. Defaults to develop."},
                "includeRaw": {"type": "boolean", "description": "Include parsed raw JSON when true. Defaults to false."},
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
                "repo": {"type": "string", "description": "Product docs repo. Defaults to loaring-story/loaring-product."},
                "ref": {"type": "string", "description": "Product docs ref. Defaults to develop."},
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
                "ref": {"type": "string", "description": "Product docs ref. Defaults to develop."},
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
        "description": "Validate cached Project Stories for missing fields, contract/status mismatches, and workflow risks. Defaults to the current GitHub Project Sprint when sprint is omitted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
                "sprint": {"type": "string"},
                "assignee": {"type": "string", "description": "GitHub login to filter Story assignees."},
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
    "loaring_prepare_doc_edit": {
        "description": "Prepare the GitHub-first document edit workflow: branch, draft PR body, and Story Issue notification comment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "target": {"type": "string", "description": "docs or contract. Defaults to docs."},
                "files": {"type": "array", "items": {"type": "string"}},
                "notifyUsers": {"type": "array", "items": {"type": "string"}, "description": "GitHub logins to @mention in the Story Issue comment."},
                "slug": {"type": "string"},
                "branch": {"type": "string"},
                "prNumber": {"type": "integer"},
                "prUrl": {"type": "string"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue"],
            "additionalProperties": False,
        },
    },
    "loaring_announce_doc_edit": {
        "description": "Post or preview the Story Issue comment that announces a GitHub document edit in progress. Writes require apply=true and confirm=true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "target": {"type": "string", "description": "docs or contract. Defaults to docs."},
                "files": {"type": "array", "items": {"type": "string"}},
                "notifyUsers": {"type": "array", "items": {"type": "string"}, "description": "GitHub logins to @mention in the Story Issue comment."},
                "slug": {"type": "string"},
                "branch": {"type": "string"},
                "prNumber": {"type": "integer"},
                "prUrl": {"type": "string"},
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["storyIssue"],
            "additionalProperties": False,
        },
    },
    "loaring_sprint_report": {
        "description": "Summarize Sprint Stories by Status, Contract Readiness, Implementation Target, and blockers. Defaults to the current GitHub Project Sprint when sprint is omitted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
                "sprint": {"type": "string"},
                "assignee": {"type": "string", "description": "GitHub login to filter Story assignees."},
            },
            "additionalProperties": False,
        },
    },
    "loaring_contract_gap_report": {
        "description": "List Stories whose API contract is required but Missing, Draft, or Blocked. Defaults to the current GitHub Project Sprint when sprint is omitted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "projectNumber": {"type": "integer"},
                "sprint": {"type": "string"},
                "assignee": {"type": "string", "description": "GitHub login to filter Story assignees."},
            },
            "additionalProperties": False,
        },
    },
    "loaring_create_api_contract_issue_comment": {
        "description": "Generate or post a standardized [계약 질문], [계약 결정], or [계약 제안] Issue comment body.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "kind": {"type": "string", "description": "question, decision, or proposal."},
                "question": {"type": "string"},
                "decision": {"type": "string"},
                "proposal": {"type": "string", "description": "Proposal payload or schema/content change summary for kind=proposal."},
                "apiSpecPath": {"type": "string"},
                "endpointId": {"type": "string"},
                "currentContract": {"type": "string"},
                "changeType": {"type": "string", "description": "additive, behavioral, breaking, or unknown."},
                "impact": {"type": "string", "description": "Provider/consumer impact summary."},
                "confirmationRequest": {"type": "string"},
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
        "description": "Check PR Story linkage across implementation/product repos and optionally move the linked Story to In Request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prNumber": {"type": "integer"},
                "storyIssue": {"type": "integer"},
                "body": {"type": "string"},
                "apply": {"type": "boolean"},
                "confirm": {"type": "boolean"},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "prRepo": {"type": "string", "description": "Repo containing the PR, e.g. owner/loaring-backend or owner/loaring-frontend. Defaults to repo."},
                "projectNumber": {"type": "integer"},
            },
            "required": ["prNumber"],
            "additionalProperties": False,
        },
    },
    "loaring_detect_work_conflicts": {
        "description": "Find open PRs that already reference the same Story or documented files before a team member starts work.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "storyIssue": {"type": "integer"},
                "target": {"type": "string", "description": "product, contract, backend, frontend, fix, docs, or chore. Defaults to docs."},
                "files": {"type": "array", "items": {"type": "string"}},
                "repo": {"type": "string", "description": "Story issue repo. Defaults to loaring-story/loaring-product."},
                "prRepos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "PR repos to scan, e.g. owner/loaring-backend and owner/loaring-frontend. Defaults from target.",
                },
            },
            "required": ["storyIssue"],
            "additionalProperties": False,
        },
    },
    "loaring_weekly_bottleneck_report": {
        "description": "Summarize plugin interaction bottleneck telemetry for the last week or a supplied time window.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "Inclusive ISO datetime. Defaults to 7 days before until."},
                "until": {"type": "string", "description": "Exclusive ISO datetime. Defaults to now."},
                "repo": {"type": "string"},
                "eventType": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "additionalProperties": False,
        },
    },
}


def available_schema_names() -> set[str]:
    return set(TOOLS)
