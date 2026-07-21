---
name: api-contract
description: "Prepare, inspect, or change LoaRing product API contracts. Default to a lightweight contract brief; create full api-spec JSON only when explicitly requested."
---

# API Contract

`loaring-product` owns final API contracts. Implementation repositories consume the contract; they do not vendor product files and do not treat each other as source of truth.

## Source Of Truth

Read from `loaring-story/loaring-product@develop` unless the user gives another repo/ref:

- `docs/contracts/registry.yml`
- `docs/contracts/error-codes.yml`
- `docs/contracts/naming-rules.yml`
- `docs/contracts/response-envelope.yml`
- `docs/api/api-catalog.yml`
- related `docs/api/*.api-spec.json`
- `docs/requirements/traceability.yml`

If `loaring-product` is not cloned, use GitHub, the GitHub connector, or:

```bash
uv run python scripts/fetch_product_contract.py
uv run python scripts/fetch_product_contract.py --path docs/api/<file>.api-spec.json
```

When the LoaRing Product Ops MCP tools are available, prefer them for lookup:

- `loaring_sync_product` to refresh the local sqlite cache from `loaring-product`
- `loaring_get_contract` to inspect linked API contract metadata
- `loaring_validate_contract_readiness` to check whether implementation can start
- `loaring_contract_gap_report` to find Stories that still need contract work
- `loaring_create_api_contract_issue_comment` to draft or, with explicit approval, post `[계약 질문]` and `[계약 결정]` comments
- `loaring_apply_workflow_transition` to move approved contract work to `In Progress` without bypassing readiness gates

The local sqlite cache is not source of truth. It may store snapshots, indexes, and drafts, but accepted contracts must live in `loaring-product`.

## Access Guardrails

Use the listed sources only when they are directly needed for the current user request. Do not broaden lookup to unrelated repositories, GitHub records, personal apps, calendars, mail, drives, or team messages based only on possible usefulness.

Limit lookup to the requested Story, requirement, API spec, repo/ref, Project field, assignee, sprint, or file path. If the needed scope is unclear or may include sensitive data, ask before lookup.

## Contract Shape

Default output is a contract brief, not a full `*.api-spec.json` file.

The contract brief should include:

- Story or requirement link
- API impact and change type
- affected or proposed `docs/api/*.api-spec.json` path
- endpoint candidates, with method/path only when there is enough evidence
- shared contract checks to perform
- contract questions and decisions
- next product action

Do not write full request/response schemas, error lists, or validation matrices unless the user explicitly asks for full API spec JSON.

Produce full `*.api-spec.json` only when the user explicitly asks for "full api-spec json", "전체 api-spec.json", "완전한 JSON spec", "API spec 파일 전체", or equivalent wording.

If the user says only "API 명세 작성" and also asks to create or edit a repository file, ask whether they want a contract brief or a full `*.api-spec.json`.

Contract brief is not sufficient for independent provider/consumer implementation. Before backend and frontend implementation starts, create or reference a full `*.api-spec.json` from `loaring-product`, or clearly mark the work as blocked by missing contract.

Full `*.api-spec.json` creation or edits must happen in `loaring-product`, not backend or frontend implementation repositories. When running outside `loaring-product`, produce a contract brief or product PR proposal instead of writing spec files.

API specs use provider/consumer language:

- endpoint contract: `method`, `path`, `auth`, `request`, `response`, `errors`
- schemas: request/response DTO shape at the wire level
- consumer guidance: `consumerGuidance.schemaNames`, `consumerGuidance.uiRules`
- validation checks: `provider`, `consumer`, `qa`

Do not add implementation repository paths such as `frontend/lib/...` or `backend/...` to product API specs.

## Registry Lookup

Before adding names, fields, envelopes, or errors in either brief or full spec mode:

1. Read `registry.yml` to find the active files.
2. Check existing error codes, endpoint naming, field naming, enum naming, pagination, sorting, filtering, auth, and response envelope rules.
3. Reuse an existing rule when semantics match.
4. If a new rule is needed, describe the proposed entry and affected API specs.

## Change Classification

| Discovery | Action |
|---|---|
| Implementation or test omission only | Fix in the implementation PR |
| Contract omission before implementation branches | Open or update a product contract PR |
| Contract change during implementation | One provider or consumer PR owns code/tests and proposes product contract change |
| Change blocks both sides or affects multiple Stories | Use an exceptional product docs-only PR |
| New user value or expanded Story scope | Create a new Story |
| Scope, schedule, priority, breaking compatibility, or owner conflict | Draft `[PM 결정 요청]` |

Change type values are `additive`, `behavioral`, `breaking`, and `unknown`.

## Workflow

1. Locate the Story, requirement IDs, affected endpoints, and existing API specs.
2. Inspect shared contract registry before inventing names or errors.
3. Default to a contract brief unless the user explicitly requested full `*.api-spec.json`.
4. In contract brief mode, propose the spec path, endpoint candidates, shared-rule checks, contract questions, and next product action.
5. In full spec mode, draft or update `docs/api/{issue}-{domain}-{feature}.api-spec.json` using `template.api-spec.json`.
6. Update `api-catalog.yml` and `traceability.yml` when links change and the user approved product doc edits.
7. Move unresolved questions to `[계약 질문]`; record accepted outcomes as `[계약 결정]`.
8. Require counterpart review: provider author needs consumer approval, consumer author needs provider approval, external author needs both.
9. For breaking changes, include a compatibility plan before merge.
10. After a full spec is accepted, use `loaring_infer_project_fields` and approved `loaring_update_project_fields` to align Project readiness.

## Output Guardrails

- Keep contract brief concise enough to paste into a Story comment or product PR description.
- Do not include implementation repository paths, database schema, service classes, frontend components, or state management details.
- Do not duplicate the same question across product, contract, and implementation sections.
- Use `[계약 질문]` for unresolved contract decisions.
- Use `[계약 결정]` only for outcomes the user says are accepted.

## External Actions

Do not post comments, open PRs, edit Project state, or mention owners until the user approves the exact GitHub action.
