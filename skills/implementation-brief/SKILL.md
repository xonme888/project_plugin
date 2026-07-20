---
name: implementation-brief
description: "Create backend, frontend, or QA implementation briefs from LoaRing product Story and API contracts without requiring implementation repositories to know each other."
---

# Implementation Brief

Use this skill to turn approved product material into implementation instructions for one role. The brief should contain product contract facts, not another repository's internal design.

## Source Of Truth

Read from `loaring-story/loaring-product@develop` unless the user gives another repo/ref:

- GitHub Story Issue
- Project fields: `Epic`, `Status`, `Sprint`, `Story Point`, `Contract Required`
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

Do not produce an implementation-ready provider or consumer brief for API work unless a full `*.api-spec.json` exists in `loaring-product`, or the user explicitly accepts a contract gap. If the contract is missing, return a blocked brief with the product contract question or proposal.

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
