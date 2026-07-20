---
name: requirement-analysis
description: "Analyze LoaRing feature requests before implementation. Use to classify raw requirements, find existing Story/API metadata, identify API impact, produce open questions, and recommend the next product action."
---

# Requirement Analysis

Requirement analysis happens before Story creation or before changing an existing Story/API contract. The result is a draft, not team agreement.

## Source Of Truth

Read from `loaring-story/loaring-product@develop` unless the user gives another repo/ref:

- `docs/requirements/requirement-analysis-template.v1.yml`
- `docs/requirements/story-map.md`
- `docs/requirements/traceability.yml`
- `docs/api/api-catalog.yml`
- related `docs/api/*.api-spec.json`
- related GitHub Story Issue or PR, if one exists

If `loaring-product` is not cloned, fetch files through GitHub or `scripts/fetch_product_contract.py --path <path>`.

When the LoaRing Product Ops MCP tools are available, prefer them for lookup:

- `loaring_sync_product` to refresh the local sqlite cache from `loaring-product`
- `loaring_sync_github` to refresh Story Issue and Project field caches
- `loaring_find_story` to search existing requirements, story-map entries, and API specs
- `loaring_find_cached_stories` to search cached GitHub Story Issues
- `loaring_get_story` to inspect Story body and Project fields
- `loaring_get_contract` to inspect linked contract metadata
- `loaring_contract_gap_report` to summarize existing contract blockers before recommending new work
- `loaring_sprint_report` to understand Sprint readiness and assignment pressure when the user asks about sequencing

The local sqlite cache is not source of truth. Treat it as a read-through cache of `loaring-product` and GitHub.

## Classification

| Situation | Result |
|---|---|
| New user value | `new-story` |
| Existing Story needs clearer acceptance criteria | `refine-existing-story` |
| Contract and implementation differ without new user value | `api-change-only` or implementation fix |
| Story Point is likely 5+ or requires multiple provider/consumer PRs | `split-story` |
| Outside current product scope | `reject` or `[PM 결정 요청]` |

## API Impact

| Change | Type |
|---|---|
| No API effect | `none` |
| New endpoint, optional field, or reusable error code | `additive` |
| Same shape but changed meaning, validation, permission, sorting, filter, or empty state | `behavioral` |
| Removed endpoint, required field change, status/error code breaking change, response shape change | `breaking` |
| Not enough evidence | `unknown` |

## Workflow

1. Separate product value, API contract impact, implementation detail, and open question.
2. Search `story-map.md` and `traceability.yml` for overlap.
3. Search existing GitHub Story Issues and Project fields when available.
4. Search `api-catalog.yml` for affected endpoint IDs and spec files.
5. Read related API specs and shared contract files when API impact exists.
6. Produce a requirement-analysis draft using the versioned template shape.
7. Recommend one next action: Story creation, Story refinement, contract question, PM decision request, implementation brief, or hold.

When recommending implementation start, check `Contract Required`, `Contract Readiness`, and `Implementation Target`. Do not recommend backend/frontend implementation while required readiness is `Missing`, `Draft`, or `Blocked`.

## External Actions

Do not update product docs, GitHub Issues, PRs, Project fields, or mentions until the user approves the exact change.
