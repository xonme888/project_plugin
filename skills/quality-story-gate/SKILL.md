---
name: quality-story-gate
description: "Read-only manual audit for the simplified LoaRing Story workflow. Use to check Story, Project, API contract, PR, review, QA, and Done readiness against docs/team-operating-model.md without mutating GitHub."
---

# Story Quality Gate

현재 4인 팀 운영 기준의 읽기 전용 점검 스킬이다. Project, Issue, PR을 수정하지 않는다.

기준 문서:

- `docs/team-operating-model.md`
- `.github/ISSUE_TEMPLATE/user-story.yml`
- `.github/pull_request_template.md`
- `docs/api/README.md`

## Project 필드

현재 Project는 최소 상태판이다.

- `Epic`
- `Status`
- `Sprint`
- `Story Point`
- `Contract Required`

담당자는 Project 필드가 아니라 GitHub assignee로 확인하고, PR 연결은 linked PR 또는 PR 본문 `Related #<issue>`로 확인한다.

## 점검 항목

| 단계 | 확인 |
| --- | --- |
| Intake | Story 목적, 시나리오, 정상/예외 인수 조건, Backend/Frontend/QA 체크리스트, 완료 조건, 미결정 사항 |
| Todo | Epic, Sprint, Story Point, Contract Required, assignee, 미결정 사항 없음 |
| Contract | `docs/api/` 계약 파일, 계약 질문/결정 기록, 계약 PR 리뷰, 문서 검증 통과 |
| Development | `be/{issue}-*`, `fe/{issue}-*` PR 또는 해당 없음 근거, API 계약 변경 단일 소유 |
| In Request | CI 통과, 최소 1명 승인, 미해결 Review Thread 없음, AI 사용 기록 |
| QA 체크 | BE/FE PR 병합, QA 체크리스트 완료, 회귀 확인 |
| Done | 완료 조건 체크, 열린 linked PR 없음, `Status=Done` 가능 |

## 검증

로컬 파일은 `docs/team-operating-model.md`, `.github/pull_request_template.md`, `docs/api/README.md`를 기준으로 수동 점검한다.

실제 GitHub Project 점검은 GitHub Project 화면 또는 GraphQL 조회로 확인한다. `gh` 인증이 없으면 원격 Project 상태를 확인했다고 말하지 않는다.
