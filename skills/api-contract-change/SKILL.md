---
name: api-contract-change
description: "Classify and prepare LoaRing API contract changes against existing docs/api metadata. Use when a requirement or implementation would change an existing API contract."
---

# API Contract Change

기존 API 변경은 코드 수정 전에 요구사항, 기존 계약, 호환성, PR 소유자를 먼저 분류한다. `docs/api`에는 확정된 계약만 기록하고, 질문과 결정은 GitHub Story Issue 또는 PR Review에 남긴다.

## Required Context

- 변경 요청 또는 구현 중 발견한 불일치
- `docs/api/api-catalog.yml`
- 관련 `docs/api/*.api-spec.json`
- `docs/requirements/traceability.yml`
- 관련 Story Issue, Project `Contract Required`, 담당 Backend/Frontend Owner
- 진행 중인 BE/FE/docs PR

## Classification

| Discovery | Action |
|-----------|--------|
| 구현 또는 테스트 누락만 있음 | 기존 구현 PR에서 수정 |
| 구현 전 계약 누락 | Story를 Contract 단계로 되돌리고 계약 PR 작성 |
| 구현 중 계약 변경 | BE 또는 FE 구현 PR 하나가 코드, 테스트, 계약을 함께 소유 |
| 양쪽 구현을 모두 차단하거나 여러 Story에 영향 | 예외적인 docs-only 계약 PR |
| 새 사용자 가치 또는 Story 범위 확장 | 새 Story로 분리 |
| 범위, 일정, 우선순위, breaking change, 합의 충돌 | Story Issue에 `[PM 결정 요청]` 초안 작성 |

## Change Types

- `additive`: 새 endpoint, 새 optional field, 새 error code처럼 기존 소비자를 깨지 않는 추가.
- `behavioral`: response shape는 같지만 의미, 정렬, 권한, validation, empty state가 바뀜.
- `breaking`: required field, status code, error code, endpoint path/method, response shape가 기존 소비자를 깸.
- `unknown`: 기존 계약이나 구현 근거가 부족함.

## Workflow

1. `docs/api/api-catalog.yml`에서 대상 spec, endpoint, requirementIds, storyIssue를 확인한다.
2. 대상 `*.api-spec.json`에서 endpoint, schema, responseCodes, errorCodes, validationChecks를 확인한다.
3. 변경 유형을 분류하고 호환성 계획 필요 여부를 판단한다.
4. 변경 소유 PR을 하나로 정한다.
5. 반대 파트 리뷰어와 승인 기준을 확인한다.
6. 미확정 내용은 `[계약 질문]` 또는 `[PM 결정 요청]` 초안으로 분리한다.
7. 확정된 변경만 API 명세와 `api-catalog.yml`에 반영한다.
8. `docs/requirements/traceability.yml`에 요구사항 연결을 갱신한다.

## Stop Conditions

- GitHub 논의 없이 제품 범위나 breaking change를 확정하지 않는다.
- 같은 API 파일 변경을 BE PR과 FE PR에 중복 반영하지 않는다.
- Project 상태, Issue 댓글, PR 댓글, mention은 사용자 승인 없이 변경하지 않는다.
