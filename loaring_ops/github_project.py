"""GitHub Project v2 write helpers for LoaRing workflow operations."""

from __future__ import annotations

import json
from typing import Any

from .config import project_number, story_repo_name
from .db import connect, init_db
from .github_client import gh_graphql, gh_graphql_json
from .github_sync import canonical_project_field_name, sync_project
from .product_sync import infer_project_fields, now_iso


CONTRACT_READINESS_OPTIONS = [
    "Not Required",
    "Missing",
    "Draft",
    "Backend Ready",
    "Frontend Ready",
    "Ready",
    "Blocked",
]

STATUS_TRANSITIONS = {
    "start-contract": "In Progress",
    "start-product": "In Progress",
    "start-backend": "In Progress",
    "start-frontend": "In Progress",
    "request-review": "In Request",
    "qa-pass": "Done",
    "complete": "Done",
    "block": "Blocked",
}


PROJECT_METADATA_QUERY = """
query($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      id
      fields(first: 100) {
        nodes {
          ... on ProjectV2Field {
            id
            name
            dataType
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            dataType
            options {
              id
              name
              color
              description
            }
          }
          ... on ProjectV2IterationField {
            id
            name
            dataType
          }
        }
      }
    }
  }
}
"""

USER_PROJECT_METADATA_QUERY = PROJECT_METADATA_QUERY.replace("organization(login: $owner)", "user(login: $owner)")

UPDATE_ITEM_FIELD_MUTATION = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId,
    itemId: $itemId,
    fieldId: $fieldId,
    value: { singleSelectOptionId: $optionId }
  }) {
    projectV2Item { id }
  }
}
"""

UPDATE_FIELD_OPTIONS_MUTATION = """
mutation($fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
  updateProjectV2Field(input: {
    fieldId: $fieldId,
    singleSelectOptions: $options
  }) {
    projectV2Field {
      ... on ProjectV2SingleSelectField {
        id
        name
        options { id name color description }
      }
    }
  }
}
"""


def update_project_fields(
    story_issue: int,
    fields: dict[str, str] | None = None,
    apply: bool = False,  # noqa: A002 - MCP argument name
    confirm: bool = False,
    repo: str | None = None,
    number: int | None = None,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    inferred = infer_project_fields(story_issue=story_issue, repo=selected_repo, number=selected_project)
    desired = fields or inferred["recommendedFields"]
    current = inferred["currentProjectFields"]
    changes = [
        {"field": key, "current": current.get(key), "desired": value}
        for key, value in desired.items()
        if current.get(key) != value
    ]
    result: dict[str, Any] = {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "storyIssue": story_issue,
        "apply": apply,
        "confirmed": confirm,
        "changes": changes,
        "inference": inferred,
    }
    if not changes:
        result["status"] = "noop"
        return result
    if not apply:
        result["status"] = "planned"
        result["message"] = "Set apply=true and confirm=true to write these Project field changes."
        return result
    require_confirm(confirm)

    item_id = cached_project_item_id(selected_repo, selected_project, story_issue)
    metadata = get_project_metadata(selected_repo, selected_project)
    applied: list[dict[str, Any]] = []
    for change in changes:
        field_meta = metadata["fields"].get(change["field"])
        if not field_meta:
            raise ValueError(f"Project field not found: {change['field']}")
        option_id = option_id_for(field_meta, str(change["desired"]))
        payload = gh_graphql(
            UPDATE_ITEM_FIELD_MUTATION,
            {
                "projectId": metadata["projectId"],
                "itemId": item_id,
                "fieldId": field_meta["id"],
                "optionId": option_id,
            },
        )
        applied.append({**change, "fieldId": field_meta["id"], "optionId": option_id, "github": payload.get("data")})
    sync_project(repo=selected_repo, number=selected_project)
    result["status"] = "applied"
    result["applied"] = applied
    result["appliedAt"] = now_iso()
    return result


def sync_contract_readiness_options(
    apply: bool = False,  # noqa: A002 - MCP argument name
    confirm: bool = False,
    repo: str | None = None,
    number: int | None = None,
) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    metadata = get_project_metadata(selected_repo, selected_project)
    field = metadata["fields"].get("Contract Readiness")
    if not field:
        raise ValueError("Contract Readiness field not found in Project.")
    current = [option["name"] for option in field.get("options", [])]
    missing = [name for name in CONTRACT_READINESS_OPTIONS if name not in current]
    extra = [name for name in current if name not in CONTRACT_READINESS_OPTIONS]
    reorder_needed = [name for name in current if name in CONTRACT_READINESS_OPTIONS] != [
        name for name in CONTRACT_READINESS_OPTIONS if name in current
    ]
    result: dict[str, Any] = {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "field": "Contract Readiness",
        "apply": apply,
        "confirmed": confirm,
        "expected": CONTRACT_READINESS_OPTIONS,
        "current": current,
        "missing": missing,
        "extra": extra,
        "reorderNeeded": reorder_needed,
    }
    if not missing and not extra and not reorder_needed:
        result["status"] = "ready"
        return result
    if not apply:
        result["status"] = "planned"
        result["message"] = "Set apply=true and confirm=true to rewrite Contract Readiness options."
        return result
    require_confirm(confirm)

    by_name = {option["name"]: option for option in field.get("options", [])}
    options = [option_input(name, by_name.get(name)) for name in CONTRACT_READINESS_OPTIONS]
    payload = gh_graphql_json(
        UPDATE_FIELD_OPTIONS_MUTATION,
        {"fieldId": field["id"], "options": options},
    )
    updated = (
        ((payload.get("data") or {}).get("updateProjectV2Field") or {})
        .get("projectV2Field")
        or {}
    )
    result["status"] = "applied"
    result["updated"] = updated
    result["appliedAt"] = now_iso()
    return result


def get_project_metadata(repo: str, number: int) -> dict[str, Any]:
    owner = repo.split("/", 1)[0]
    try:
        payload = gh_graphql(PROJECT_METADATA_QUERY, {"owner": owner, "number": number})
        project = ((payload.get("data") or {}).get("organization") or {}).get("projectV2")
    except RuntimeError:
        payload = gh_graphql(USER_PROJECT_METADATA_QUERY, {"owner": owner, "number": number})
        project = ((payload.get("data") or {}).get("user") or {}).get("projectV2")
    if not project:
        raise ValueError(f"Project #{number} not found for {owner}.")
    fields: dict[str, dict[str, Any]] = {}
    for node in ((project.get("fields") or {}).get("nodes") or []):
        if not node or not node.get("name"):
            continue
        name = canonical_project_field_name(str(node["name"]))
        fields[name] = {**node, "name": name}
    return {"projectId": project["id"], "fields": fields}


def cached_project_item_id(repo: str, number: int, story_issue: int) -> str:
    conn = connect()
    init_db(conn)
    row = conn.execute(
        "SELECT item_id FROM project_items WHERE repo = ? AND project_number = ? AND issue_number = ?",
        (repo, number, story_issue),
    ).fetchone()
    if row and row["item_id"]:
        return str(row["item_id"])
    raise ValueError("Project item id is not cached. Run loaring_sync_project before writing fields.")


def option_id_for(field_meta: dict[str, Any], option_name: str) -> str:
    for option in field_meta.get("options") or []:
        if option.get("name") == option_name:
            return str(option["id"])
    raise ValueError(f"{field_meta.get('name')} option not found: {option_name}")


def option_input(name: str, existing: dict[str, Any] | None) -> dict[str, Any]:
    colors = {
        "Not Required": "GRAY",
        "Missing": "RED",
        "Draft": "YELLOW",
        "Backend Ready": "BLUE",
        "Frontend Ready": "PURPLE",
        "Ready": "GREEN",
        "Blocked": "RED",
    }
    descriptions = {
        "Not Required": "Story does not require an API contract.",
        "Missing": "A required API contract has not been linked.",
        "Draft": "A contract exists but is not implementation-ready.",
        "Backend Ready": "Provider-side backend implementation may start.",
        "Frontend Ready": "Consumer-side frontend implementation may start.",
        "Ready": "Backend and frontend implementation may start.",
        "Blocked": "A contract decision blocks implementation.",
    }
    payload = {
        "name": name,
        "color": (existing or {}).get("color") or colors[name],
        "description": (existing or {}).get("description") or descriptions[name],
    }
    if existing and existing.get("id"):
        payload["id"] = existing["id"]
    return payload


def require_confirm(confirmed: bool) -> None:
    if not confirmed:
        raise ValueError("confirm=true is required for GitHub write operations.")


def encode_fields(fields: dict[str, Any]) -> str:
    return json.dumps(fields, ensure_ascii=False, sort_keys=True)
