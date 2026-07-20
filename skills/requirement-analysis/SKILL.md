---
name: requirement-analysis
description: "Analyze LoaRing feature requests before implementation. Use to turn raw requirements into Story candidates, API impact, existing contract metadata checks, open questions, and next actions."
---

# Requirement Analysis

요구사항 분석은 GitHub Story Issue 생성 전 또는 기존 Story/API 변경 판단 전에 수행한다. 분석 결과는 확정 합의가 아니며, GitHub Story Issue와 PR Review의 결정을 대체하지 않는다.

## Required Context

- 사용자 요청 또는 회의 메모
- `docs/requirements/story-map.md`
- `docs/requirements/traceability.yml`
- `docs/api/api-catalog.yml`
- 관련 `docs/api/*.api-spec.json`
- 관련 GitHub Story Issue 또는 PR이 있으면 그 내용

## Workflow

1. 요구사항이 새 사용자 가치인지, 기존 Story 보완인지, API 변경만 필요한지 분류한다.
2. `docs/requirements/story-map.md`에서 같은 가치나 충돌 후보를 찾는다.
3. `docs/requirements/traceability.yml`에서 연결된 Story, API 명세, PR, 테스트를 확인한다.
4. `docs/api/api-catalog.yml`에서 기존 endpoint와 변경 정책을 확인한다.
5. API 영향이 있으면 변경 유형을 `none`, `additive`, `behavioral`, `breaking`, `unknown` 중 하나로 분류한다.
6. 미확정 제품 범위, 계약 질문, 기술 질문을 분리한다.
7. `docs/requirements/requirement-analysis-template.v1.yml` 구조에 맞춰 분석 초안을 작성한다.
8. Story가 필요하면 `docs/requirements/user-story-template.v1.yml`과 `.github/ISSUE_TEMPLATE/user-story.yml` 기준으로 Story 초안을 만든다.

## Decision Rules

| 상황 | 판단 |
|------|------|
| 새 사용자 가치가 있다 | `new-story` |
| 기존 Story의 인수 조건이 부족하다 | `refine-existing-story` |
| 구현과 계약이 불일치하지만 사용자 가치가 바뀌지 않는다 | `api-change-only` 또는 구현 PR 수정 |
| Story Point 5 이상이거나 BE/FE PR이 여러 개 필요하다 | `split-story` |
| 현재 제품 범위 밖이다 | `reject` 또는 `[PM 결정 요청]` |

## API Impact Rules

| 변경 | changeType |
|------|------------|
| API 영향 없음 | `none` |
| 새 endpoint, 새 optional field, 새 error code 추가 | `additive` |
| 같은 shape지만 의미, validation, 권한, 정렬, 필터 동작 변경 | `behavioral` |
| endpoint 삭제, required field 변경, response shape 변경, status/error code breaking 변경 | `breaking` |
| 근거가 부족함 | `unknown` |

## Output

- 요구사항 분류
- 기존 Story/API와의 관계
- API 영향과 변경 유형
- 미결정 질문
- 다음 액션: Story 생성, 계약 질문, PM 결정 요청, 구현 가능, 보류 중 하나

Project 상태, Issue 댓글, PR 댓글, mention은 사용자가 명시적으로 승인하기 전에는 변경하지 않는다.
