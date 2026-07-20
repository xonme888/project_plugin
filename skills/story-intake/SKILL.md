---
name: story-intake
description: "Create or refine LoaRing product Story issues and backlog entries. Use for Story scope, acceptance criteria, Epic, Sprint, Story Point, assignees, contract fields, implementation target, and GitHub Project readiness without creating Task or Epic issues."
---

# Story Intake

GitHub Story Issue is the source of truth for user value, scenarios, acceptance criteria, work scope, QA, and done criteria. Do not create separate Story documents, Task issues, or Epic issues.

## Source Of Truth

Read from `loaring-story/loaring-product@develop` unless the user gives another repo/ref:

- `.github/ISSUE_TEMPLATE/user-story.yml`
- `.github/story-project-schema.json`
- `docs/requirements/user-story-template.v1.yml`
- `docs/requirements/story-map.md`
- `docs/requirements/traceability.yml`

If `loaring-product` is not cloned, fetch files through GitHub or `scripts/fetch_product_contract.py --path <path>`.

When the LoaRing Product Ops MCP tools are available, prefer them for lookup:

- `loaring_sync_product` to refresh product docs
- `loaring_sync_github` to refresh Story Issues and Project fields
- `loaring_find_story` and `loaring_find_cached_stories` to check duplicate or related value
- `loaring_get_story` to inspect an existing Story and Project fields
- `loaring_infer_project_fields` to check `Contract Required`, `Contract Readiness`, and `Implementation Target`

The local sqlite cache is not source of truth. Treat it as a read-through cache of `loaring-product` and GitHub.

## Required Story Data

- Purpose and user value
- As a / I want / So that
- Acceptance criteria for normal and exception flows
- Provider / consumer / QA checklist, kept as short responsibility-level checks, with `해당 없음` when a role has no work
- Done criteria, written as user-observable outcomes
- Open questions or `없음`
- Epic, Story Point, Contract Required, Contract Readiness, Implementation Target, Sprint when known
- GitHub assignees for owner roles

## Scope Level

Story intake produces a product Story, not an implementation plan.

- Keep the Story readable enough to fit comfortably in a GitHub Issue.
- Acceptance criteria should describe user-observable behavior, not internal classes, database tables, components, or endpoint lists.
- Backend, Frontend, and QA sections should be short checklists that identify responsibility boundaries only.
- Do not duplicate the same condition across acceptance criteria, QA, and done criteria unless it changes meaning.
- Put endpoint shapes, request/response fields, error codes, and compatibility details in `api-contract`.
- Put role-specific implementation steps, test scope, and repository-specific details in `implementation-brief`.

Default checklist size:

- Backend: 2-4 items
- Frontend: 2-4 items
- QA: 2-4 scenario-level items
- Done: 3-5 user-observable outcomes

## Workflow

1. Check `story-map.md` and `traceability.yml` for duplicate or related value.
2. Check existing GitHub Story Issues and Project fields when available.
3. Draft with `user-story-template.v1.yml`.
4. If the Story should be created in GitHub, map the draft to `.github/ISSUE_TEMPLATE/user-story.yml`.
5. Use only Project fields: `Epic`, `Status`, `Sprint`, `Story Point`, `Contract Required`, `Contract Readiness`, `Implementation Target`.
6. Keep owner assignment in GitHub assignees, not custom Project fields.
7. If API work is needed, hand off to `api-contract`.
8. If the Story draft needs detailed backend, frontend, or QA execution steps, hand off to `implementation-brief`.
9. After a GitHub Issue number exists, update `traceability.yml`.

## External Actions

Do not create Issues, edit Project fields, post comments, or mention people until the user explicitly approves the exact GitHub action.
