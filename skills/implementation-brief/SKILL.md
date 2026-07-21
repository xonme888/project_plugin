---
name: implementation-brief
description: "Create backend, frontend, or QA implementation briefs from LoaRing product Story and API contracts without requiring implementation repositories to know each other."
---

# Implementation Brief

Use this skill to turn approved product material into implementation instructions for one role. The brief should contain product contract facts, not another repository's internal design.

## Source Of Truth

Read from `loaring-story/loaring-product@develop` unless the user gives another repo/ref:

- GitHub Story Issue
- Project fields: `Epic`, `Status`, `Sprint`, `Story Point`, `Contract Required`, `Contract Readiness`, `Implementation Target`
- `docs/requirements/traceability.yml`
- related `docs/api/*.api-spec.json`
- `docs/contracts/*.yml` when errors, naming, or envelope rules matter

If `loaring-product` is not cloned, fetch files through GitHub or `scripts/fetch_product_contract.py --path <path>`.

When the LoaRing Product Ops MCP tools are available, start with:

- `loaring_sync_product` when the local cache is stale or empty
- `loaring_sync_github` when Story body or Project fields may be stale
- `loaring_get_story` to inspect Story body, assignees, and Project fields
- `loaring_validate_contract_readiness` before producing provider or consumer briefs for API work
- `loaring_get_contract` to retrieve linked API contract metadata
- `loaring_infer_project_fields` to verify contract fields and implementation target
- `loaring_plan_story_work` to decide whether implementation can start and which branch target applies
- `loaring_prepare_branch` to produce the standard branch name when the user asks for branch preparation
- `loaring_create_work_branch` to create the branch only after the user approves the exact repo and target
- `loaring_validate_branch_name` to check implementation repo branch naming before coding or PR work
- `loaring_prepare_pr` to draft a PR title/body with `Related #...` and contract readiness context
- `loaring_link_pr_to_project` to check PR linkage and, with approval, move the Story to `In Request`

Do not produce an implementation-ready provider or consumer brief for API work unless a full `*.api-spec.json` exists in `loaring-product`, or the user explicitly accepts a contract gap. If the contract is missing, return a blocked brief with the product contract question or proposal.

Interpret `Contract Readiness` strictly:

- `Backend Ready` allows backend/provider implementation only.
- `Frontend Ready` allows frontend/consumer implementation only.
- `Ready` allows both backend and frontend implementation.
- `Missing`, `Draft`, and `Blocked` do not allow implementation-ready briefs unless the user explicitly accepts the gap.

Use `loaring_apply_workflow_transition` before implementation state changes. `start-backend` requires `Backend Ready` or `Ready`; `start-frontend` requires `Frontend Ready` or `Ready`; `request-review` is blocked while readiness is `Missing`, `Draft`, or `Blocked`.

## Access Guardrails

Use the listed sources only when they are directly needed for the current user request. Do not broaden lookup to unrelated repositories, GitHub records, personal apps, calendars, mail, drives, or team messages based only on possible usefulness.

Limit lookup to the requested Story, requirement, API spec, repo/ref, Project field, assignee, sprint, or file path. If the needed scope is unclear or may include sensitive data, ask before lookup.

## Provider Brief

Include only:

- Story number, user value, acceptance criteria
- approved endpoint, request, response, status code, error code, validation, auth, envelope
- provider test scope
- contract questions or PM decision request drafts
- explicit non-goals and change limits

Do not include consumer file paths, components, state management, or UI implementation details.

## Consumer Brief

Include only:

- Story number, user value, acceptance criteria
- approved endpoint, request, response, error handling, `consumerGuidance.uiRules`
- screen states and manual verification scope
- contract questions or PM decision request drafts
- explicit non-goals and change limits

Do not include provider packages, entities, database schema, service classes, or server implementation details.

## QA Brief

Include only:

- Story done criteria
- normal and exception scenarios
- API contract checks that can be externally observed
- regression risks
- unresolved decisions that block testing

## Contract Drift

If implementation needs a contract change, do not assume local implementation docs are source of truth. Hand off to `api-contract` and draft the product Story/PR question before changing the contract.
