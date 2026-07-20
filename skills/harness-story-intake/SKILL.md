---
name: harness-story-intake
description: "Create or refine LoaRing GitHub Story issues for the simplified 4-person workflow. Use for Story scope, acceptance criteria, Epic, Sprint, Story Point, assignees, and Contract Required decisions without creating Epic or Task issues."
---

# Story Intake

GitHub Story Issue가 사용자 가치, 시나리오, 인수 조건, 작업 범위, QA, 완료 조건의 단일 원본이다. Epic Issue와 Task Issue는 만들지 않는다.

## Required Story Data

- 목적
- As a / I want / So that
- 인수 조건: 정상 흐름, 예외 상황
- Backend / Frontend / QA 체크리스트
- 완료 조건
- 미결정 사항 또는 `없음`
- Epic
- Story Point
- Contract Required: `Yes` 또는 `No`
- Sprint: `Backlog` 단계에서는 비워둘 수 있음
- Backend/Frontend 담당자: GitHub assignee로 관리

## Versioned Templates

- Story 생성 전 초안은 `docs/requirements/user-story-template.v1.yml`을 기준으로 작성한다.
- 전체 Story 후보와 누락 점검은 `docs/requirements/story-map.md`를 확인한다.
- Issue 생성 후에는 `docs/requirements/traceability.yml`에 요구사항, Story Issue, API 명세, PR, 테스트 연결을 남긴다.
- GitHub Issue 입력 폼은 `.github/ISSUE_TEMPLATE/user-story.yml`이지만, 템플릿 버전 관리는 `docs/requirements/user-story-template.v1.yml`에서 한다.

## Project 필드

Project에는 다음 필드만 사용한다.

- `Epic`
- `Status`
- `Sprint`
- `Story Point`
- `Contract Required`

담당자는 Project 필드가 아니라 GitHub assignee로 관리한다. PR 연결은 linked PR과 PR 본문 `Related #<issue>`로 확인한다.

## Workflow

1. `docs/requirements/story-map.md`에서 같은 사용자 가치의 기존 후보나 Story가 있는지 확인한다.
2. `docs/requirements/traceability.yml`에서 기존 Story/API 연결을 확인한다.
3. 새 가치라면 `docs/requirements/user-story-template.v1.yml`로 Story 초안을 작성한다.
4. GitHub 등록 시 `.github/ISSUE_TEMPLATE/user-story.yml`로 Story를 작성한다.
5. Project에 추가하고 `Epic`, `Story Point`, `Contract Required`를 채운다.
6. Sprint와 작업 범위가 확정되기 전이면 `Status=Backlog`로 둔다.
7. Sprint와 작업 범위가 확정되면 `Status=Todo`로 둔다.
8. 담당자는 Issue assignee로 지정한다.
9. API 계약이 필요하면 `harness-api-contract` 또는 `api-contract-change`로 넘긴다.
10. Story Issue 번호가 생기면 `docs/requirements/traceability.yml`을 갱신한다.

미결정 사항이 있으면 구현을 시작하지 않는다. 제품 범위, 일정, 우선순위, 페어 간 충돌은 Story Issue에 `[PM 결정 요청]`으로 남기고, 진행이 막히면 `Status=Blocked`로 표시한 뒤 차단 사유를 Story Issue에 남긴다.

Project 또는 Issue 변경은 사용자가 명시적으로 승인한 경우에만 수행한다.
