---
name: harness-story-delivery
description: "Coordinate Backend and Frontend implementation for a LoaRing Story using the simplified Project model, Story-linked branches, linked PRs, review, QA, and Done checks."
---

# Story Delivery

한 Story는 필요하면 Backend PR과 Frontend PR로 분리한다. 공유 연결 키는 GitHub Issue 번호다.

## Branches

모든 작업 브랜치는 `develop`에서 시작한다.

```txt
docs/{issue}-{slug}-contract
be/{issue}-{slug}
fe/{issue}-{slug}
```

PR 본문에는 `Related #<issue>`를 포함한다. Project에는 PR URL을 저장하지 않는다.

## Implementation

- Backend 변경은 `loaring-backend`, Frontend 변경은 `loaring-frontend`의 독립 PR로 처리한다.
- 구현 중 API 계약 변경이 필요하면 product Story 또는 product PR에 변경 요청을 남긴다.
- 확정되지 않은 계약 변경을 BE/FE 구현 PR에 먼저 고정하지 않는다.
- 계약 변경 PR은 product repo에서 리뷰하고, 확정 후 각 구현 저장소가 반영한다.

## Project Status

Project 상태는 수동으로 관리한다.

| Status | 기준 |
| --- | --- |
| `Todo` | 작업 범위, `Sprint`, 담당자, `Contract Required` 확정 |
| `In Progress` | BE 또는 FE 구현 진행 |
| `In Request` | PR 리뷰 요청 |
| `Blocked` | 결정·병목·외부 이슈로 진행 불가 |
| `Done` | QA와 완료 조건 충족 |

## Review and QA

PR은 다음을 보여줘야 한다.

- 관련 Story
- API 계약 또는 변경 없음
- AI 사용 범위
- 테스트/빌드/수동 검증 결과
- 남은 리스크

병합 전 확인:

- CI 통과
- 최소 1명 승인
- 미해결 Review Thread 없음
- API 계약과 구현 일치
- 계약 변경 중복 없음

Done 전 확인:

- BE/FE 필요한 PR 병합
- QA 체크리스트 완료
- 완료 조건 체크
- 열린 linked PR 없음

Project, Issue, PR 상태 변경은 사용자가 명시적으로 승인한 경우에만 수행한다.
