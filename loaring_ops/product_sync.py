"""Read-only product metadata synchronization."""

from __future__ import annotations

import re
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .config import PRODUCT_PATHS, legacy_story_repos, project_number, repo_name, repo_ref, story_repo_name
from .db import connect, init_db
from .github_client import fetch_file
from .safety import operation_lock


KST = timezone(timedelta(hours=9), "KST")


CONTRACT_READINESS_VALUES = {
    "Not Required",
    "Missing",
    "Draft",
    "Backend Ready",
    "Frontend Ready",
    "Ready",
    "Blocked",
}


def now_iso() -> str:
    return datetime.now(KST).isoformat()


def sync_product(repo: str | None = None, ref: str | None = None) -> dict[str, Any]:
    selected_repo = repo_name(repo)
    selected_ref = repo_ref(ref)
    with operation_lock("sync-product-cache"):
        return _sync_product_locked(selected_repo, selected_ref)


def _sync_product_locked(selected_repo: str, selected_ref: str) -> dict[str, Any]:
    fetched_at = now_iso()
    conn = connect()
    init_db(conn)

    fetched: list[dict[str, Any]] = []
    for path in PRODUCT_PATHS:
        fetched.append(fetch_and_save_snapshot(conn, selected_repo, selected_ref, path, fetched_at))

    catalog_content = snapshot(conn, "docs/api/api-catalog.yml", selected_repo, selected_ref)
    if catalog_content:
        known_paths = {item["path"] for item in fetched}
        for spec in parse_api_catalog(catalog_content):
            path = spec.get("path")
            if isinstance(path, str) and path and path not in known_paths:
                fetched.append(fetch_and_save_snapshot(conn, selected_repo, selected_ref, path, fetched_at))
                known_paths.add(path)

    index_cached_product(conn, selected_repo, selected_ref, fetched_at)
    conn.execute(
        """
        INSERT INTO sync_state (source, repo, ref, last_synced_at)
        VALUES ('product-docs', ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
          repo = excluded.repo,
          ref = excluded.ref,
          last_synced_at = excluded.last_synced_at
        """,
        (selected_repo, selected_ref, fetched_at),
    )
    conn.commit()
    return {"repo": selected_repo, "ref": selected_ref, "fetchedAt": fetched_at, "files": fetched}


def fetch_and_save_snapshot(
    conn: sqlite3.Connection,
    repo: str,
    ref: str,
    path: str,
    fetched_at: str,
) -> dict[str, str | None]:
    content, sha = fetch_file(repo, ref, path)
    conn.execute(
        """
        INSERT INTO product_snapshots (repo, ref, path, sha, content, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo, ref, path) DO UPDATE SET
          sha = excluded.sha,
          content = excluded.content,
          fetched_at = excluded.fetched_at
        """,
        (repo, ref, path, sha, content, fetched_at),
    )
    return {"path": path, "sha": sha}


def snapshot(conn: sqlite3.Connection, path: str, repo: str | None = None, ref: str | None = None) -> str | None:
    row = conn.execute(
        """
        SELECT content FROM product_snapshots
        WHERE path = ?
          AND (? IS NULL OR repo = ?)
          AND (? IS NULL OR ref = ?)
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (path, repo, repo, ref, ref),
    ).fetchone()
    return None if row is None else str(row["content"])


def index_cached_product(conn: sqlite3.Connection, repo: str | None, ref: str | None, updated_at: str) -> None:
    if repo is None or ref is None:
        raise ValueError("repo and ref are required when indexing product docs.")
    catalog_content = snapshot(conn, "docs/api/api-catalog.yml", repo, ref)
    if catalog_content:
        for spec in parse_api_catalog(catalog_content):
            conn.execute(
                """
                INSERT INTO api_specs (
                  repo, ref, path, domain, title, story_issue, requirement_ids_json,
                  endpoints_json, lifecycle, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo, ref, path) DO UPDATE SET
                  domain = excluded.domain,
                  title = excluded.title,
                  story_issue = excluded.story_issue,
                  requirement_ids_json = excluded.requirement_ids_json,
                  endpoints_json = excluded.endpoints_json,
                  lifecycle = excluded.lifecycle,
                  updated_at = excluded.updated_at
                """,
                (
                    repo,
                    ref,
                    spec.get("path"),
                    spec.get("domain"),
                    spec.get("title"),
                    spec.get("storyIssue"),
                    json.dumps(spec.get("requirementIds") or [], ensure_ascii=False),
                    json.dumps(spec.get("endpoints") or [], ensure_ascii=False),
                    spec.get("lifecycle"),
                    updated_at,
                ),
            )

    trace_content = snapshot(conn, "docs/requirements/traceability.yml", repo, ref)
    if trace_content:
        for req in parse_traceability(trace_content):
            conn.execute(
                """
                INSERT INTO requirements (
                  repo, ref, requirement_id, title, status, epic, story_issues_json,
                  api_specs_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo, ref, requirement_id) DO UPDATE SET
                  title = excluded.title,
                  status = excluded.status,
                  epic = excluded.epic,
                  story_issues_json = excluded.story_issues_json,
                  api_specs_json = excluded.api_specs_json,
                  updated_at = excluded.updated_at
                """,
                (
                    repo,
                    ref,
                    req.get("id"),
                    req.get("title"),
                    req.get("status"),
                    req.get("epic"),
                    json.dumps(req.get("storyIssues") or [], ensure_ascii=False),
                    json.dumps(req.get("apiSpecs") or [], ensure_ascii=False),
                    updated_at,
                ),
            )


def find_story(query: str, limit: int = 10, repo: str | None = None, ref: str | None = None) -> dict[str, Any]:
    selected_repo = repo_name(repo)
    selected_ref = repo_ref(ref)
    conn = connect()
    init_db(conn)
    like = f"%{query}%"
    req_rows = conn.execute(
        """
        SELECT * FROM requirements
        WHERE repo = ? AND ref = ?
          AND (requirement_id LIKE ? OR title LIKE ? OR epic LIKE ?)
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (selected_repo, selected_ref, like, like, like, limit),
    ).fetchall()
    spec_rows = conn.execute(
        """
        SELECT * FROM api_specs
        WHERE repo = ? AND ref = ?
          AND (path LIKE ? OR title LIKE ? OR domain LIKE ?)
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (selected_repo, selected_ref, like, like, like, limit),
    ).fetchall()
    story_map = snapshot(conn, "docs/requirements/story-map.md", selected_repo, selected_ref)
    story_map_hits = search_story_map(story_map or "", query, limit)
    return {
        "repo": selected_repo,
        "ref": selected_ref,
        "requirements": [decode_json_fields(dict(row)) for row in req_rows],
        "apiSpecs": [decode_json_fields(dict(row)) for row in spec_rows],
        "storyMapHits": story_map_hits,
    }


def get_contract(
    story_issue: int | None = None,
    requirement_id: str | None = None,
    repo: str | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    selected_repo = repo_name(repo)
    selected_ref = repo_ref(ref)
    conn = connect()
    init_db(conn)
    specs: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []

    if requirement_id:
        req_row = conn.execute(
            "SELECT * FROM requirements WHERE repo = ? AND ref = ? AND requirement_id = ?",
            (selected_repo, selected_ref, requirement_id),
        ).fetchone()
        if req_row:
            req = decode_json_fields(dict(req_row))
            requirements.append(req)
            for path in req.get("api_specs", []):
                spec_row = conn.execute(
                    "SELECT * FROM api_specs WHERE repo = ? AND ref = ? AND path = ?",
                    (selected_repo, selected_ref, path),
                ).fetchone()
                if spec_row:
                    specs.append(decode_json_fields(dict(spec_row)))

    if story_issue is not None:
        for row in conn.execute(
            "SELECT * FROM api_specs WHERE repo = ? AND ref = ? AND story_issue = ?",
            (selected_repo, selected_ref, story_issue),
        ).fetchall():
            specs.append(decode_json_fields(dict(row)))
        for row in conn.execute(
            "SELECT * FROM requirements WHERE repo = ? AND ref = ?",
            (selected_repo, selected_ref),
        ).fetchall():
            req = decode_json_fields(dict(row))
            if story_issue in req.get("story_issues", []):
                requirements.append(req)

    return {
        "repo": selected_repo,
        "ref": selected_ref,
        "storyIssue": story_issue,
        "requirementId": requirement_id,
        "requirements": requirements,
        "apiSpecs": dedupe_by_path(specs),
    }


def resolve_contract_target(
    query: str | None = None,
    story_issue: int | None = None,
    requirement_id: str | None = None,
    api_spec_path: str | None = None,
    repo: str | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """Resolve legacy Story/API/requirement hints to one product contract target."""
    selected_repo = repo_name(repo)
    selected_ref = repo_ref(ref)
    selected_story_repo = story_repo_name(None if repo == selected_repo else repo)
    selected_project = project_number(None)
    conn = connect()
    init_db(conn)

    warnings: list[str] = []
    candidate_map: dict[tuple[int | None, str | None, str | None], dict[str, Any]] = {}

    def add_candidate(
        canonical_story: int | None,
        req_id: str | None,
        spec_path: str | None,
        score: int,
        reasons: list[str],
        legacy_refs: list[dict[str, Any]] | None = None,
    ) -> None:
        key = (canonical_story, req_id, spec_path)
        current = candidate_map.get(key)
        if current is None:
            candidate_map[key] = {
                "canonicalStoryIssue": canonical_story,
                "requirementId": req_id,
                "apiSpecPath": spec_path,
                "score": score,
                "reasons": reasons,
                "legacyIssueReferences": legacy_refs or [],
            }
            return
        current["score"] += score
        current["reasons"].extend(reasons)
        current["legacyIssueReferences"] = dedupe_issue_refs(current["legacyIssueReferences"] + (legacy_refs or []))

    if api_spec_path:
        spec = api_spec_by_path(conn, selected_repo, selected_ref, api_spec_path)
        if spec:
            for req_id in spec.get("requirement_ids") or [None]:
                add_candidate(spec.get("story_issue"), req_id, spec.get("path"), 100, ["matched apiSpecPath"])
        else:
            warnings.append(f"No cached API spec index found for {api_spec_path}.")

    if requirement_id:
        req = requirement_by_id(conn, selected_repo, selected_ref, requirement_id)
        if req:
            for path in req.get("api_specs") or [None]:
                linked_spec = api_spec_by_path(conn, selected_repo, selected_ref, path) if path else None
                story_values = req.get("story_issues") or [None]
                for issue in story_values:
                    add_candidate(
                        linked_spec.get("story_issue") if linked_spec else issue,
                        req.get("requirement_id"),
                        path,
                        95,
                        ["matched requirementId"],
                    )
        else:
            warnings.append(f"No cached requirement found for {requirement_id}.")

    if story_issue is not None:
        for spec in api_specs_by_story(conn, selected_repo, selected_ref, story_issue):
            for req_id in spec.get("requirement_ids") or [None]:
                add_candidate(story_issue, req_id, spec.get("path"), 90, ["matched product Story issue"])
        for req in requirements_by_story(conn, selected_repo, selected_ref, story_issue):
            for path in req.get("api_specs") or [None]:
                add_candidate(story_issue, req.get("requirement_id"), path, 85, ["matched traceability Story issue"])

        primary_story = latest_story(conn, selected_story_repo, story_issue)
        if primary_story:
            add_candidates_from_story_title(
                conn,
                selected_repo,
                selected_ref,
                selected_story_repo,
                primary_story,
                story_issue,
                add_candidate,
                ["matched cached product Story"],
                70,
            )
        else:
            legacy_ref = find_legacy_story(conn, story_issue)
            if legacy_ref:
                add_candidates_from_story_title(
                    conn,
                    selected_repo,
                    selected_ref,
                    selected_story_repo,
                    legacy_ref,
                    story_issue,
                    add_candidate,
                    ["mapped legacy Story by normalized title"],
                    80,
                )
            else:
                warnings.append(f"No cached product or legacy Story found for issue #{story_issue}.")

    if query:
        like = f"%{query}%"
        for spec_row in conn.execute(
            """
            SELECT * FROM api_specs
            WHERE repo = ? AND ref = ?
              AND (path LIKE ? OR title LIKE ? OR domain LIKE ? OR endpoints_json LIKE ? OR requirement_ids_json LIKE ?)
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (selected_repo, selected_ref, like, like, like, like, like),
        ).fetchall():
            spec = decode_json_fields(dict(spec_row))
            for req_id in spec.get("requirement_ids") or [None]:
                add_candidate(spec.get("story_issue"), req_id, spec.get("path"), 45, ["matched API catalog query"])
        for req_row in conn.execute(
            """
            SELECT * FROM requirements
            WHERE repo = ? AND ref = ?
              AND (requirement_id LIKE ? OR title LIKE ? OR epic LIKE ? OR api_specs_json LIKE ?)
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (selected_repo, selected_ref, like, like, like, like),
        ).fetchall():
            req = decode_json_fields(dict(req_row))
            for issue in req.get("story_issues") or [None]:
                for path in req.get("api_specs") or [None]:
                    add_candidate(issue, req.get("requirement_id"), path, 40, ["matched traceability query"])
        for story_row in cached_story_query(conn, selected_story_repo, query, 20):
            story = decode_cached_story(dict(story_row))
            add_candidates_from_story_title(
                conn,
                selected_repo,
                selected_ref,
                selected_story_repo,
                story,
                story.get("issue_number"),
                add_candidate,
                ["matched cached Story query"],
                35,
            )

    candidates = [
        enrich_contract_candidate(conn, item, selected_repo, selected_ref, selected_story_repo, selected_project)
        for item in candidate_map.values()
    ]
    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected = candidates[0] if candidates else None
    if len(candidates) > 1:
        top_score = candidates[0]["score"]
        ambiguous = [item for item in candidates if item["score"] >= top_score - 20]
        if len(ambiguous) > 1:
            warnings.append("Multiple plausible contract targets matched; use candidates to disambiguate.")
    confidence = candidate_confidence(candidates)
    return {
        "repo": selected_repo,
        "ref": selected_ref,
        "canonicalRepo": selected_repo,
        "canonicalStoryIssue": None if selected is None else selected.get("canonicalStoryIssue"),
        "legacyIssueReferences": [] if selected is None else selected.get("legacyIssueReferences", []),
        "requirementId": None if selected is None else selected.get("requirementId"),
        "apiSpecPath": None if selected is None else selected.get("apiSpecPath"),
        "apiSpec": None if selected is None else selected.get("apiSpec"),
        "endpointIds": [] if selected is None else selected.get("endpointIds", []),
        "projectFields": None if selected is None else selected.get("projectFields"),
        "confidence": confidence,
        "warnings": warnings,
        "candidates": candidates[:10],
    }


def get_api_spec(
    path: str | None = None,
    story_issue: int | None = None,
    requirement_id: str | None = None,
    endpoint_id: str | None = None,
    repo: str | None = None,
    ref: str | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    selected_repo = repo_name(repo)
    selected_ref = repo_ref(ref)
    resolved_path = path
    warnings: list[str] = []
    if resolved_path is None:
        resolved = resolve_contract_target(
            story_issue=story_issue,
            requirement_id=requirement_id,
            query=endpoint_id,
            repo=selected_repo,
            ref=selected_ref,
        )
        resolved_path = resolved.get("apiSpecPath")
        warnings.extend(resolved.get("warnings") or [])
    conn = connect()
    init_db(conn)
    spec_index = api_spec_by_path(conn, selected_repo, selected_ref, resolved_path) if resolved_path else None
    if spec_index:
        resolved_path = spec_index.get("path")
    content = snapshot(conn, resolved_path, selected_repo, selected_ref) if resolved_path else None
    parsed = parse_api_spec_json(content)
    if not resolved_path or not parsed:
        return {
            "repo": selected_repo,
            "ref": selected_ref,
            "path": resolved_path,
            "status": "missing",
            "warnings": warnings + ["No cached api-spec JSON snapshot found."],
            "rawJsonAvailable": bool(content),
        }

    endpoints = parsed.get("endpoints") if isinstance(parsed.get("endpoints"), list) else []
    if endpoint_id:
        endpoints = [item for item in endpoints if isinstance(item, dict) and item.get("id") == endpoint_id]
        if not endpoints:
            warnings.append(f"No endpoint matched endpointId={endpoint_id}.")
    schema_defs = parsed.get("schemas") if isinstance(parsed.get("schemas"), dict) else {}
    endpoint_summaries = [summarize_endpoint(item, schema_defs) for item in endpoints if isinstance(item, dict)]
    validation = parsed.get("validationChecks") if isinstance(parsed.get("validationChecks"), dict) else {}
    return {
        "repo": selected_repo,
        "ref": selected_ref,
        "path": resolved_path,
        "lifecycle": (spec_index or {}).get("lifecycle"),
        "title": ((parsed.get("meta") or {}).get("title") if isinstance(parsed.get("meta"), dict) else None)
        or (spec_index or {}).get("title"),
        "storyIssue": (spec_index or {}).get("story_issue"),
        "requirementIds": (spec_index or {}).get("requirement_ids", []),
        "endpoints": endpoint_summaries,
        "requestSchemas": [item["request"] for item in endpoint_summaries],
        "responseSchemas": [item["response"] for item in endpoint_summaries],
        "errors": parsed.get("errorCodes") or [],
        "responseCodes": parsed.get("responseCodes") or [],
        "validationRules": validation,
        "consumerGuidance": [
            {"endpointId": item.get("id"), **(item.get("consumerGuidance") or {})}
            for item in endpoints
            if isinstance(item, dict) and item.get("consumerGuidance")
        ],
        "uiRules": [
            rule
            for item in endpoints
            if isinstance(item, dict)
            for rule in ((item.get("consumerGuidance") or {}).get("uiRules") or [])
        ],
        "rawJsonAvailable": True,
        "rawJson": parsed if include_raw else None,
        "warnings": warnings,
    }


def validate_contract_readiness(
    story_issue: int | None = None,
    requirement_id: str | None = None,
    repo: str | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    selected_repo = repo_name(repo)
    selected_ref = repo_ref(ref)
    contract = get_contract(story_issue=story_issue, requirement_id=requirement_id, repo=selected_repo, ref=selected_ref)
    conn = connect()
    init_db(conn)
    specs = enrich_specs_with_readiness(conn, contract["apiSpecs"], None, selected_repo, selected_ref)
    issues: list[str] = []
    if not specs:
        issues.append("No linked full api-spec entry found in api-catalog.yml.")
    for spec in specs:
        if spec.get("lifecycle") not in {"accepted", "review", "draft"}:
            issues.append(f"{spec.get('path')}: lifecycle is missing or unknown.")
        if not spec.get("endpoints"):
            issues.append(f"{spec.get('path')}: no endpoints indexed.")
    readiness = infer_contract_readiness("Yes", {"apiSpecs": specs}, None)
    ready = readiness == "Ready" and not issues
    return {
        "ready": ready,
        "status": readiness,
        "issues": issues,
        "contract": {**contract, "apiSpecs": specs},
    }


def infer_project_fields(
    story_issue: int | None = None,
    requirement_id: str | None = None,
    repo: str | None = None,
    ref: str | None = None,
    number: int | None = None,
) -> dict[str, Any]:
    """Infer project field values from cached product docs and Story metadata."""
    if story_issue is None and requirement_id is None:
        raise ValueError("storyIssue or requirementId is required")

    selected_repo = story_repo_name(repo)
    selected_product_repo = repo_name()
    selected_ref = repo_ref(ref)
    selected_project = project_number(number)
    conn = connect()
    init_db(conn)

    contract = get_contract(story_issue=story_issue, requirement_id=requirement_id, repo=selected_product_repo, ref=selected_ref)
    story = latest_story(conn, selected_repo, story_issue)
    project_fields = latest_project_fields(conn, selected_repo, selected_project, story_issue)

    contract_required = infer_contract_required(contract, story)
    enriched_specs = enrich_specs_with_readiness(conn, contract["apiSpecs"], story, selected_product_repo, selected_ref)
    enriched_contract = {**contract, "apiSpecs": enriched_specs}
    contract_readiness = infer_contract_readiness(contract_required, enriched_contract, story)
    implementation_target = infer_implementation_target(contract_required, contract, story)
    recommended = {
        "Contract Required": contract_required,
        "Contract Readiness": contract_readiness,
        "Implementation Target": implementation_target,
    }
    mismatches = [
        {"field": key, "current": project_fields.get(key), "recommended": value}
        for key, value in recommended.items()
        if project_fields.get(key) not in {None, "", value}
    ]
    return {
        "repo": selected_repo,
        "productRepo": selected_product_repo,
        "ref": selected_ref,
        "projectNumber": selected_project,
        "storyIssue": story_issue,
        "requirementId": requirement_id,
        "recommendedFields": recommended,
        "currentProjectFields": project_fields,
        "mismatches": mismatches,
        "evidence": {
            "story": minimal_story(story),
            "requirements": enriched_contract["requirements"],
            "apiSpecs": enriched_contract["apiSpecs"],
        },
    }


def latest_story(conn: sqlite3.Connection, repo: str, story_issue: int | None) -> dict[str, Any] | None:
    if story_issue is None:
        return None
    row = conn.execute(
        """
        SELECT * FROM stories
        WHERE repo = ? AND issue_number = ?
        ORDER BY synced_at DESC
        LIMIT 1
        """,
        (repo, story_issue),
    ).fetchone()
    if row is None:
        return None
    story = dict(row)
    story["labels"] = json.loads(story.pop("labels_json") or "[]")
    story["assignees"] = json.loads(story.pop("assignees_json") or "[]")
    return story


def latest_project_fields(
    conn: sqlite3.Connection,
    repo: str,
    selected_project: int,
    story_issue: int | None,
) -> dict[str, Any]:
    if story_issue is None:
        return {}
    row = conn.execute(
        """
        SELECT fields_json FROM project_items
        WHERE repo = ? AND project_number = ? AND issue_number = ?
        ORDER BY synced_at DESC
        LIMIT 1
        """,
        (repo, selected_project, story_issue),
    ).fetchone()
    if row is None:
        return {}
    return json.loads(row["fields_json"] or "{}")


def infer_contract_required(contract: dict[str, Any], story: dict[str, Any] | None) -> str:
    if contract["apiSpecs"]:
        return "Yes"
    text = story_text(story)
    if re.search(r"Contract Required\s*\n\s*Yes", text, flags=re.IGNORECASE):
        return "Yes"
    if re.search(r"API\s*명세\s*\n\s*docs/api/", text, flags=re.IGNORECASE):
        return "Yes"
    if any(keyword in text for keyword in ["API 계약", "API 연동", "응답", "요청"]):
        return "Yes"
    return "No"


def infer_contract_readiness(
    contract_required: str,
    contract: dict[str, Any],
    story: dict[str, Any] | None = None,
) -> str:
    if contract_required == "No":
        return "Not Required"
    specs = contract["apiSpecs"]
    if not specs:
        return "Missing"
    if any(not spec.get("endpoints") or not spec.get("lifecycle") for spec in specs):
        return "Blocked"
    lifecycles = {spec.get("lifecycle") for spec in specs}
    if lifecycles & {"draft", "review"}:
        return "Draft"
    evaluations = [spec_readiness_evaluation(spec, story) for spec in specs]
    if any(item["blocked"] for item in evaluations):
        return "Blocked"
    backend_ready = all(item["backendReady"] for item in evaluations)
    frontend_ready = all(item["frontendReady"] for item in evaluations)
    frontend_excluded = frontend_scope_excluded(story) or any(item["frontendExcluded"] for item in evaluations)
    if backend_ready and frontend_ready and not frontend_excluded:
        return "Ready"
    if backend_ready and not frontend_ready:
        return "Backend Ready"
    if backend_ready and frontend_excluded:
        return "Backend Ready"
    if frontend_ready and not backend_ready:
        return "Frontend Ready"
    if lifecycles <= {"accepted"}:
        return "Draft"
    return "Blocked"


def infer_implementation_target(
    contract_required: str,
    contract: dict[str, Any],
    story: dict[str, Any] | None,
) -> str:
    text = story_text(story)
    if "요구사항 정리" in text or "requirements clarification" in text.lower():
        return "Product"
    if frontend_scope_excluded(story) and (contract_required == "Yes" or contract["apiSpecs"]):
        return "Backend"
    if contract_required == "Yes" or contract["apiSpecs"]:
        return "Backend+Frontend"
    if "QA" in text and "Backend" not in text and "Frontend" not in text:
        return "QA"
    return "Product"


def story_text(story: dict[str, Any] | None) -> str:
    if not story:
        return ""
    return f"{story.get('title') or ''}\n{story.get('body') or ''}"


def enrich_specs_with_readiness(
    conn: sqlite3.Connection,
    specs: list[dict[str, Any]],
    story: dict[str, Any] | None,
    repo: str,
    ref: str,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for spec in specs:
        content = snapshot(conn, str(spec.get("path") or ""), repo, ref)
        parsed = parse_api_spec_json(content) if content else {}
        evaluation = spec_readiness_evaluation({**spec, "spec": parsed}, story)
        enriched.append({**spec, "readinessEvidence": evaluation})
    return enriched


def parse_api_spec_json(content: str | None) -> dict[str, Any]:
    if not content:
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def spec_readiness_evaluation(spec: dict[str, Any], story: dict[str, Any] | None) -> dict[str, Any]:
    existing = spec.get("readinessEvidence")
    if isinstance(existing, dict):
        return existing
    parsed = spec.get("spec") if isinstance(spec.get("spec"), dict) else {}
    endpoints = parsed.get("endpoints") if isinstance(parsed, dict) else None
    endpoint_list = endpoints if isinstance(endpoints, list) else spec.get("endpoints") or []
    response_codes = parsed.get("responseCodes") if isinstance(parsed, dict) else []
    error_codes = parsed.get("errorCodes") if isinstance(parsed, dict) else []
    validation = parsed.get("validationChecks") if isinstance(parsed, dict) else {}

    provider_checks = validation.get("provider") if isinstance(validation, dict) else []
    consumer_checks = validation.get("consumer") if isinstance(validation, dict) else []
    qa_checks = validation.get("qa") if isinstance(validation, dict) else []
    endpoint_details = [item for item in endpoint_list if isinstance(item, dict)]

    backend_ready = bool(endpoint_details) and all(
        has_endpoint_provider_shape(item) for item in endpoint_details
    ) and bool(response_codes) and bool(error_codes) and bool(provider_checks)

    consumer_guidance_count = sum(1 for item in endpoint_details if item.get("consumerGuidance"))
    frontend_excluded = frontend_scope_excluded(story) or excluded_consumer_checks(consumer_checks)
    frontend_ready = (
        bool(endpoint_details)
        and all(has_endpoint_consumer_shape(item) for item in endpoint_details)
        and consumer_guidance_count == len(endpoint_details)
        and bool(consumer_checks)
        and not frontend_excluded
    )
    qa_ready = bool(qa_checks)
    blocked = not endpoint_details
    return {
        "backendReady": backend_ready,
        "frontendReady": frontend_ready,
        "qaReady": qa_ready,
        "frontendExcluded": frontend_excluded,
        "blocked": blocked,
        "consumerGuidanceEndpoints": consumer_guidance_count,
        "endpointCount": len(endpoint_details),
        "notes": readiness_notes(backend_ready, frontend_ready, qa_ready, frontend_excluded),
    }


def has_endpoint_provider_shape(endpoint: dict[str, Any]) -> bool:
    request = endpoint.get("request")
    response = endpoint.get("response")
    return all(endpoint.get(key) for key in ["id", "method", "path"]) and isinstance(request, dict) and isinstance(response, dict)


def has_endpoint_consumer_shape(endpoint: dict[str, Any]) -> bool:
    response = endpoint.get("response")
    if not isinstance(response, dict):
        return False
    return bool(response.get("bodySchema") is not None or response.get("example") is not None)


def frontend_scope_excluded(story: dict[str, Any] | None) -> bool:
    text = story_text(story)
    return bool(re.search(r"Frontend\s*\n\s*-\s*\[[ xX]\]\s*이번 Sprint 범위 제외", text))


def excluded_consumer_checks(checks: Any) -> bool:
    if not isinstance(checks, list):
        return False
    return any(isinstance(item, str) and "이번 Sprint 범위 제외" in item for item in checks)


def readiness_notes(
    backend_ready: bool,
    frontend_ready: bool,
    qa_ready: bool,
    frontend_excluded: bool,
) -> list[str]:
    notes: list[str] = []
    if backend_ready:
        notes.append("Backend implementation has method/path/request/response/error/test evidence.")
    if frontend_ready:
        notes.append("Frontend implementation has response/example/consumer guidance evidence.")
    if frontend_excluded:
        notes.append("Frontend scope is explicitly excluded for this Story or spec.")
    if qa_ready:
        notes.append("QA checks are present.")
    return notes


def minimal_story(story: dict[str, Any] | None) -> dict[str, Any] | None:
    if not story:
        return None
    return {
        "issueNumber": story.get("issue_number"),
        "title": story.get("title"),
        "state": story.get("state"),
        "url": story.get("url"),
        "labels": story.get("labels"),
        "assignees": story.get("assignees"),
    }


def api_spec_by_path(conn: sqlite3.Connection, repo: str, ref: str, path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    row = conn.execute(
        "SELECT * FROM api_specs WHERE repo = ? AND ref = ? AND path = ?",
        (repo, ref, path),
    ).fetchone()
    if row is None and "/" not in path:
        row = conn.execute(
            "SELECT * FROM api_specs WHERE repo = ? AND ref = ? AND path LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (repo, ref, f"%/{path}"),
        ).fetchone()
    return decode_json_fields(dict(row)) if row else None


def api_specs_by_story(conn: sqlite3.Connection, repo: str, ref: str, story_issue: int) -> list[dict[str, Any]]:
    return [
        decode_json_fields(dict(row))
        for row in conn.execute(
            "SELECT * FROM api_specs WHERE repo = ? AND ref = ? AND story_issue = ?",
            (repo, ref, story_issue),
        ).fetchall()
    ]


def requirement_by_id(conn: sqlite3.Connection, repo: str, ref: str, requirement_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM requirements WHERE repo = ? AND ref = ? AND requirement_id = ?",
        (repo, ref, requirement_id),
    ).fetchone()
    return decode_json_fields(dict(row)) if row else None


def requirements_by_story(conn: sqlite3.Connection, repo: str, ref: str, story_issue: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in conn.execute("SELECT * FROM requirements WHERE repo = ? AND ref = ?", (repo, ref)).fetchall():
        req = decode_json_fields(dict(row))
        if story_issue in req.get("story_issues", []):
            result.append(req)
    return result


def find_legacy_story(conn: sqlite3.Connection, issue_number: int) -> dict[str, Any] | None:
    for legacy_repo in legacy_story_repos():
        story = latest_story(conn, legacy_repo, issue_number)
        if story:
            story["repo"] = legacy_repo
            return story
    return None


def cached_story_query(conn: sqlite3.Connection, primary_repo: str, query: str, limit: int) -> list[sqlite3.Row]:
    repos = [primary_repo]
    repos.extend(item for item in legacy_story_repos() if item not in repos)
    like = f"%{query}%"
    return conn.execute(
        """
        SELECT * FROM stories
        WHERE repo IN (%s) AND (title LIKE ? OR body LIKE ?)
        ORDER BY updated_at DESC
        LIMIT ?
        """ % ",".join("?" for _ in repos),
        (*repos, like, like, limit),
    ).fetchall()


def decode_cached_story(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["labels"] = json.loads(data.pop("labels_json") or "[]")
    data["assignees"] = json.loads(data.pop("assignees_json") or "[]")
    return data


def add_candidates_from_story_title(
    conn: sqlite3.Connection,
    product_repo: str,
    ref: str,
    primary_story_repo: str,
    story: dict[str, Any],
    input_issue: int | None,
    add_candidate: Callable[[int | None, str | None, str | None, int, list[str], list[dict[str, Any]] | None], None],
    reasons: list[str],
    score: int,
) -> None:
    title = normalize_story_title(str(story.get("title") or ""))
    if not title:
        return
    primary_matches = conn.execute(
        "SELECT * FROM stories WHERE repo = ?",
        (primary_story_repo,),
    ).fetchall()
    legacy_refs: list[dict[str, Any]] = []
    story_repo = str(story.get("repo") or "")
    if story_repo in legacy_story_repos() or (input_issue is not None and story.get("issue_number") != input_issue):
        legacy_refs.append(
            {
                "repo": story_repo or None,
                "issue": input_issue or story.get("issue_number"),
                "title": story.get("title"),
                "mappedBy": "normalized-title",
            }
        )
    for row in primary_matches:
        primary = decode_cached_story(dict(row))
        if normalize_story_title(str(primary.get("title") or "")) != title:
            continue
        canonical_issue = int(primary["issue_number"])
        refs = list(legacy_refs)
        if input_issue is not None and input_issue != canonical_issue:
            refs.append(
                {
                    "repo": story_repo or find_legacy_repo_for_issue(conn, input_issue),
                    "issue": input_issue,
                    "title": story.get("title"),
                    "mappedTo": f"{primary_story_repo}#{canonical_issue}",
                    "mappedBy": "normalized-title",
                }
            )
        specs = api_specs_by_story(conn, product_repo, ref, canonical_issue)
        reqs = requirements_by_story(conn, product_repo, ref, canonical_issue)
        for spec in specs:
            for req_id in spec.get("requirement_ids") or [None]:
                add_candidate(canonical_issue, req_id, spec.get("path"), score, reasons, refs)
        for req in reqs:
            for path in req.get("api_specs") or [None]:
                add_candidate(canonical_issue, req.get("requirement_id"), path, score - 5, reasons, refs)


def find_legacy_repo_for_issue(conn: sqlite3.Connection, issue_number: int) -> str | None:
    for legacy_repo in legacy_story_repos():
        if latest_story(conn, legacy_repo, issue_number):
            return legacy_repo
    return None


def enrich_contract_candidate(
    conn: sqlite3.Connection,
    candidate: dict[str, Any],
    repo: str,
    ref: str,
    story_repo: str,
    selected_project: int,
) -> dict[str, Any]:
    spec = api_spec_by_path(conn, repo, ref, candidate.get("apiSpecPath"))
    story_issue = candidate.get("canonicalStoryIssue")
    parsed = parse_api_spec_json(snapshot(conn, candidate.get("apiSpecPath") or "", repo, ref))
    endpoints = spec.get("endpoints", []) if spec else []
    endpoint_ids = [item.get("id") for item in endpoints if isinstance(item, dict) and item.get("id")]
    project_fields = latest_project_fields(conn, story_repo, selected_project, story_issue) if story_issue else {}
    return {
        **candidate,
        "canonicalRepo": repo,
        "apiSpec": None
        if spec is None
        else {
            "path": spec.get("path"),
            "title": spec.get("title")
            or ((parsed.get("meta") or {}).get("title") if isinstance(parsed.get("meta"), dict) else None),
            "domain": spec.get("domain"),
            "lifecycle": spec.get("lifecycle"),
        },
        "endpointIds": endpoint_ids,
        "projectFields": project_fields,
        "legacyIssueReferences": dedupe_issue_refs(candidate.get("legacyIssueReferences", [])),
    }


def dedupe_issue_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any]] = set()
    result: list[dict[str, Any]] = []
    for ref in refs:
        key = (ref.get("repo"), ref.get("issue"))
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def candidate_confidence(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "none"
    if len(candidates) == 1:
        return "high" if candidates[0]["score"] >= 80 else "medium"
    if candidates[0]["score"] - candidates[1]["score"] >= 30:
        return "high"
    if candidates[0]["score"] >= 80:
        return "medium"
    return "low"


def summarize_endpoint(endpoint: dict[str, Any], schemas: dict[str, Any]) -> dict[str, Any]:
    request = endpoint.get("request") if isinstance(endpoint.get("request"), dict) else {}
    response = endpoint.get("response") if isinstance(endpoint.get("response"), dict) else {}
    request_schema = request.get("bodySchema")
    response_schema = response.get("bodySchema")
    return {
        "id": endpoint.get("id"),
        "method": endpoint.get("method"),
        "path": endpoint.get("path"),
        "summary": endpoint.get("summary"),
        "auth": endpoint.get("auth"),
        "request": {
            "contentType": request.get("contentType"),
            "pathParams": summarize_params(request.get("pathParams")),
            "queryParams": summarize_params(request.get("queryParams")),
            "bodySchema": request_schema,
            "body": summarize_schema_ref(request_schema, schemas),
            "exampleAvailable": request.get("example") is not None,
        },
        "response": {
            "httpStatus": response.get("httpStatus"),
            "code": response.get("code"),
            "bodySchema": response_schema,
            "body": summarize_schema_ref(response_schema, schemas),
            "exampleAvailable": response.get("example") is not None,
        },
        "errors": endpoint.get("errors") or [],
        "consumerGuidance": endpoint.get("consumerGuidance") or {},
    }


def summarize_params(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: {
            "type": item.get("type") if isinstance(item, dict) else None,
            "required": item.get("required") if isinstance(item, dict) else None,
        }
        for key, item in value.items()
    }


def summarize_schema_ref(schema_name: Any, schemas: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(schema_name, str) or schema_name not in schemas:
        return None
    schema = schemas[schema_name]
    if not isinstance(schema, dict):
        return None
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    return {
        "schema": schema_name,
        "type": schema.get("type"),
        "required": schema.get("required") or [],
        "fields": [
            {
                "name": name,
                "type": details.get("type") if isinstance(details, dict) else None,
                "format": details.get("format") if isinstance(details, dict) else None,
                "constraints": (details.get("constraints") or []) if isinstance(details, dict) else [],
                "description": details.get("description") if isinstance(details, dict) else None,
            }
            for name, details in properties.items()
        ],
    }


def normalize_story_title(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"^\[story\]\s*", "", normalized)
    return re.sub(r"\s+", " ", normalized)


def decode_json_fields(row: dict[str, Any]) -> dict[str, Any]:
    renamed = dict(row)
    for old, new in [
        ("requirement_ids_json", "requirement_ids"),
        ("endpoints_json", "endpoints"),
        ("story_issues_json", "story_issues"),
        ("api_specs_json", "api_specs"),
    ]:
        if old in renamed:
            renamed[new] = json.loads(renamed.pop(old) or "[]")
    return renamed


def dedupe_by_path(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for spec in specs:
        path = str(spec.get("path"))
        if path in seen:
            continue
        seen.add(path)
        result.append(spec)
    return result


def search_story_map(content: str, query: str, limit: int) -> list[str]:
    terms = [term for term in re.split(r"\s+", query.strip()) if term]
    if not terms:
        return []
    hits: list[str] = []
    for line in content.splitlines():
        if any(term.lower() in line.lower() for term in terms):
            hits.append(line)
            if len(hits) >= limit:
                break
    return hits


def parse_api_catalog(content: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_endpoints = False

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("- path:"):
            if current:
                specs.append(current)
            current = {
                "path": scalar(stripped.split(":", 1)[1]),
                "endpoints": [],
            }
            in_endpoints = False
            continue
        if current is None:
            continue
        if stripped.startswith("domain:"):
            current["domain"] = scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("title:"):
            current["title"] = scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("storyIssue:"):
            current["storyIssue"] = int_or_none(scalar(stripped.split(":", 1)[1]))
        elif stripped.startswith("requirementIds:"):
            current["requirementIds"] = inline_list(stripped.split(":", 1)[1])
        elif stripped.startswith("lifecycle:"):
            current["lifecycle"] = scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("endpoints:"):
            in_endpoints = True
        elif in_endpoints and stripped.startswith("- id:"):
            current["endpoints"].append({"id": scalar(stripped.split(":", 1)[1])})
        elif in_endpoints and stripped.startswith("changePolicy:") and current["endpoints"]:
            current["endpoints"][-1]["changePolicy"] = scalar(stripped.split(":", 1)[1])

    if current:
        specs.append(current)
    return specs


def parse_traceability(content: str) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    active_list: str | None = None

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- id:"):
            if current:
                requirements.append(current)
            current = {"id": scalar(stripped.split(":", 1)[1]), "storyIssues": [], "apiSpecs": []}
            active_list = None
            continue
        if current is None:
            continue
        if stripped.startswith("title:"):
            current["title"] = scalar(stripped.split(":", 1)[1])
            active_list = None
        elif stripped.startswith("status:"):
            current["status"] = scalar(stripped.split(":", 1)[1])
            active_list = None
        elif stripped.startswith("epic:"):
            current["epic"] = scalar(stripped.split(":", 1)[1])
            active_list = None
        elif stripped.startswith("storyIssues:"):
            current["storyIssues"] = [int(item) for item in inline_list(stripped.split(":", 1)[1]) if str(item).isdigit()]
            active_list = "storyIssues"
        elif stripped.startswith("apiSpecs:"):
            current["apiSpecs"] = inline_list(stripped.split(":", 1)[1])
            active_list = "apiSpecs"
        elif stripped.endswith(":"):
            active_list = None
        elif stripped.startswith("- ") and active_list == "apiSpecs":
            current["apiSpecs"].append(scalar(stripped[2:]))

    if current:
        requirements.append(current)
    return requirements


def scalar(value: str) -> str:
    cleaned = value.strip()
    if cleaned in {"null", "None", "~"}:
        return ""
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        return cleaned[1:-1]
    return cleaned


def inline_list(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    if not (cleaned.startswith("[") and cleaned.endswith("]")):
        return []
    inner = cleaned[1:-1].strip()
    if not inner:
        return []
    return [scalar(part) for part in inner.split(",")]


def int_or_none(value: str) -> int | None:
    return int(value) if value.isdigit() else None
