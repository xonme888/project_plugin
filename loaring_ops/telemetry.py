"""Best-effort bottleneck telemetry for MCP tool interactions."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import telemetry_db_path
from .product_sync import now_iso


JsonDict = dict[str, Any]

SCHEMA = """
CREATE TABLE IF NOT EXISTS bottleneck_events (
  id TEXT PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  event_type TEXT NOT NULL,
  status TEXT,
  repo TEXT,
  story_issue INTEGER,
  requirement_id TEXT,
  api_spec_path TEXT,
  endpoint_id TEXT,
  apply INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0,
  blocker_count INTEGER NOT NULL DEFAULT 0,
  confidence TEXT,
  error_type TEXT,
  error_message TEXT,
  summary TEXT,
  details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_bottleneck_events_occurred_at
  ON bottleneck_events (occurred_at);

CREATE INDEX IF NOT EXISTS idx_bottleneck_events_type
  ON bottleneck_events (event_type, occurred_at);
"""


def log_tool_bottlenecks_best_effort(
    tool_name: str,
    arguments: JsonDict,
    result: Any,
    error: BaseException | None,
    duration_ms: int,
) -> None:
    """Persist bottleneck events without affecting the tool result."""
    try:
        events = extract_bottleneck_events(tool_name, arguments, result, error, duration_ms)
        if not events:
            return
        insert_events(events)
    except Exception:
        if os.environ.get("LOARING_PRODUCT_OPS_TELEMETRY_DEBUG"):
            raise


def extract_bottleneck_events(
    tool_name: str,
    arguments: JsonDict,
    result: Any,
    error: BaseException | None,
    duration_ms: int,
) -> list[JsonDict]:
    base = base_event(tool_name, arguments, result, duration_ms)
    if error is not None:
        event_type = (
            "stale_cache_recovery_failed"
            if "automatic read-only sync failed" in str(error)
            else "tool_exception"
        )
        return [
            {
                **base,
                "eventType": event_type,
                "status": "error",
                "errorType": type(error).__name__,
                "errorMessage": truncate(str(error), 500),
                "summary": truncate(str(error), 240),
            }
        ]
    if not isinstance(result, dict):
        return []

    events: list[JsonDict] = []
    status = str(result.get("status") or "")
    warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    blockers = collect_blockers(result)

    if tool_name == "loaring_resolve_contract_target":
        confidence = result.get("confidence")
        if result.get("canonicalStoryIssue") is None:
            events.append(event(base, "target_resolution_failed", result, "No canonical Story target resolved."))
        elif confidence in {"none", "low"}:
            events.append(event(base, "low_confidence_resolution", result, f"Resolution confidence is {confidence}."))
        if warnings:
            ambiguity = any("Multiple plausible contract targets" in str(item) for item in warnings)
            if ambiguity:
                events.append(event(base, "target_resolution_ambiguous", result, "; ".join(map(str, warnings[:3]))))

    if tool_name == "loaring_get_api_spec":
        if status == "missing":
            events.append(event(base, "missing_api_spec_snapshot", result, "Cached api-spec JSON snapshot is missing."))
        if warnings:
            endpoint_missing = any("No endpoint matched" in str(item) for item in warnings)
            if endpoint_missing:
                events.append(event(base, "spec_endpoint_missing", result, "; ".join(map(str, warnings[:3]))))

    if result.get("syncRecovery"):
        events.append(
            event(base, "stale_cache_recovered", result, "Stale cache was recovered by automatic read-only sync.")
        )

    if status in {"blocked", "failed", "missing"} and not events:
        event_type = (
            "workflow_transition_blocked"
            if tool_name == "loaring_apply_workflow_transition"
            else "tool_result_blocked"
        )
        summary = "; ".join(map(str, blockers[:3])) or f"Tool returned status={status}."
        events.append(event(base, event_type, result, summary))

    if blockers and not any(item["eventType"].endswith("blocked") for item in events):
        events.append(event(base, "apply_blocked_by_safety_gate", result, "; ".join(map(str, blockers[:3]))))

    return events


def base_event(tool_name: str, arguments: JsonDict, result: Any, duration_ms: int) -> JsonDict:
    result_dict = result if isinstance(result, dict) else {}
    return {
        "id": str(uuid.uuid4()),
        "occurredAt": now_iso(),
        "toolName": tool_name,
        "repo": first_text(arguments.get("repo"), result_dict.get("repo"), result_dict.get("canonicalRepo")),
        "storyIssue": first_int(
            arguments.get("storyIssue"),
            result_dict.get("storyIssue"),
            result_dict.get("canonicalStoryIssue"),
        ),
        "requirementId": first_text(arguments.get("requirementId"), result_dict.get("requirementId")),
        "apiSpecPath": first_text(
            arguments.get("apiSpecPath"),
            arguments.get("path"),
            result_dict.get("apiSpecPath"),
            result_dict.get("path"),
        ),
        "endpointId": first_text(arguments.get("endpointId")),
        "apply": bool(arguments.get("apply")),
        "durationMs": max(0, duration_ms),
    }


def event(base: JsonDict, event_type: str, result: JsonDict, summary: str) -> JsonDict:
    warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    blockers = collect_blockers(result)
    return {
        **base,
        "id": str(uuid.uuid4()),
        "eventType": event_type,
        "status": result.get("status"),
        "warningCount": len(warnings),
        "blockerCount": len(blockers),
        "confidence": result.get("confidence"),
        "summary": truncate(summary, 500),
        "details": {
            "warnings": warnings[:5],
            "blockers": blockers[:5],
        },
    }


def insert_events(events: list[JsonDict]) -> None:
    path = telemetry_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=0.1)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            """
            INSERT INTO bottleneck_events (
              id, occurred_at, tool_name, event_type, status, repo, story_issue,
              requirement_id, api_spec_path, endpoint_id, apply, duration_ms,
              warning_count, blocker_count, confidence, error_type, error_message,
              summary, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    item["occurredAt"],
                    item["toolName"],
                    item["eventType"],
                    item.get("status"),
                    item.get("repo"),
                    item.get("storyIssue"),
                    item.get("requirementId"),
                    item.get("apiSpecPath"),
                    item.get("endpointId"),
                    1 if item.get("apply") else 0,
                    item.get("durationMs") or 0,
                    item.get("warningCount") or 0,
                    item.get("blockerCount") or 0,
                    item.get("confidence"),
                    item.get("errorType"),
                    item.get("errorMessage"),
                    item.get("summary"),
                    json.dumps(item.get("details") or {}, ensure_ascii=False),
                )
                for item in events
            ],
        )
        conn.commit()
    finally:
        conn.close()


def weekly_bottleneck_report(
    since: str | None = None,
    until: str | None = None,
    repo: str | None = None,
    event_type: str | None = None,
    limit: int = 20,
) -> JsonDict:
    path = telemetry_db_path()
    if not path.exists():
        return empty_report(since, until, repo, event_type, limit)
    start, end = report_window(since, until)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        rows = query_events(conn, start, end, repo, event_type, limit)
    finally:
        conn.close()
    events = [decode_event(row) for row in rows]
    by_type = Counter(item["eventType"] for item in events)
    by_tool = Counter(item["toolName"] for item in events)
    return {
        "telemetryDb": str(path),
        "since": start,
        "until": end,
        "repo": repo,
        "eventType": event_type,
        "eventCount": len(events),
        "byEventType": dict(by_type.most_common()),
        "byTool": dict(by_tool.most_common()),
        "topTargets": top_targets(events),
        "examples": examples_by_type(events),
        "recommendedFixes": recommended_fixes(by_type),
        "events": events[:limit],
    }


def query_events(
    conn: sqlite3.Connection,
    since: str,
    until: str,
    repo: str | None,
    event_type: str | None,
    limit: int,
) -> list[sqlite3.Row]:
    clauses = ["occurred_at >= ?", "occurred_at < ?"]
    values: list[Any] = [since, until]
    if repo:
        clauses.append("repo = ?")
        values.append(repo)
    if event_type:
        clauses.append("event_type = ?")
        values.append(event_type)
    values.append(max(1, min(limit, 200)))
    return conn.execute(
        f"""
        SELECT * FROM bottleneck_events
        WHERE {' AND '.join(clauses)}
        ORDER BY occurred_at DESC
        LIMIT ?
        """,
        values,
    ).fetchall()


def report_window(since: str | None, until: str | None) -> tuple[str, str]:
    if until:
        end = parse_report_datetime(until)
    else:
        end = datetime.now(timezone(timedelta(hours=9), "KST"))
    if since:
        start = parse_report_datetime(since)
    else:
        start = end - timedelta(days=7)
    return start.isoformat(), end.isoformat()


def parse_report_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone(timedelta(hours=9), "KST"))
    return parsed


def decode_event(row: sqlite3.Row) -> JsonDict:
    return {
        "id": row["id"],
        "occurredAt": row["occurred_at"],
        "toolName": row["tool_name"],
        "eventType": row["event_type"],
        "status": row["status"],
        "repo": row["repo"],
        "storyIssue": row["story_issue"],
        "requirementId": row["requirement_id"],
        "apiSpecPath": row["api_spec_path"],
        "endpointId": row["endpoint_id"],
        "apply": bool(row["apply"]),
        "durationMs": row["duration_ms"],
        "warningCount": row["warning_count"],
        "blockerCount": row["blocker_count"],
        "confidence": row["confidence"],
        "errorType": row["error_type"],
        "errorMessage": row["error_message"],
        "summary": row["summary"],
        "details": json.loads(row["details_json"] or "{}"),
    }


def examples_by_type(events: list[JsonDict]) -> dict[str, list[JsonDict]]:
    grouped: dict[str, list[JsonDict]] = {}
    for item in events:
        examples = grouped.setdefault(item["eventType"], [])
        if len(examples) >= 3:
            continue
        examples.append(
            {
                "occurredAt": item["occurredAt"],
                "toolName": item["toolName"],
                "storyIssue": item["storyIssue"],
                "apiSpecPath": item["apiSpecPath"],
                "summary": item["summary"],
            }
        )
    return grouped


def top_targets(events: list[JsonDict]) -> list[JsonDict]:
    counter: Counter[tuple[Any, Any]] = Counter()
    for item in events:
        key = (item.get("storyIssue"), item.get("apiSpecPath"))
        if key != (None, None):
            counter[key] += 1
    return [
        {"storyIssue": story, "apiSpecPath": path, "count": count}
        for (story, path), count in counter.most_common(10)
    ]


def recommended_fixes(counts: Counter[str]) -> list[str]:
    fixes: list[str] = []
    if counts["target_resolution_ambiguous"]:
        fixes.append("Add canonical aliases or explicit legacy mappings for repeated ambiguous Story/API targets.")
    if counts["missing_api_spec_snapshot"]:
        fixes.append(
            "Make product sync verify api-catalog entries have fetched JSON snapshots and surface retry guidance."
        )
    if counts["spec_endpoint_missing"]:
        fixes.append("Improve endpointId suggestions by listing nearest endpoint ids when a lookup misses.")
    if counts["stale_cache_recovered"] or counts["stale_cache_recovery_failed"]:
        fixes.append("Review cache freshness windows and extend automatic read-only sync to remaining apply tools.")
    if counts["workflow_transition_blocked"] or counts["apply_blocked_by_safety_gate"]:
        fixes.append("Include the next required contract or Project-field action in blocked workflow results.")
    if counts["tool_exception"]:
        fixes.append("Inspect tool exceptions and convert repeated failures into structured recovery instructions.")
    return fixes


def empty_report(
    since: str | None,
    until: str | None,
    repo: str | None,
    event_type: str | None,
    limit: int,
) -> JsonDict:
    start, end = report_window(since, until)
    return {
        "telemetryDb": str(telemetry_db_path()),
        "since": start,
        "until": end,
        "repo": repo,
        "eventType": event_type,
        "eventCount": 0,
        "byEventType": {},
        "byTool": {},
        "topTargets": [],
        "examples": {},
        "recommendedFixes": [],
        "events": [],
        "message": "No bottleneck telemetry has been recorded yet.",
        "limit": limit,
    }


def collect_blockers(value: Any) -> list[Any]:
    blockers: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "blockers" and isinstance(item, list):
                blockers.extend(item)
            elif isinstance(item, (dict, list)):
                blockers.extend(collect_blockers(item))
    elif isinstance(value, list):
        for item in value:
            blockers.extend(collect_blockers(item))
    return blockers


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def first_int(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."
