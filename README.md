# LoaRing Product Ops Plugin

Codex에서 LoaRing의 product 운영을 돕는 독립 플러그인 프로젝트다.

이 플러그인은 제품 데이터의 원본이 아니다. 원본은 `loaring-product` 저장소이며, 이 플러그인은 Codex가 그 원본을 조회해서 Story, 요구사항, API 계약, 구현 지시서를 다루도록 돕는다.

## 저장소 관계

```txt
loaring-product
  - Story, 요구사항, API 계약, 공통 계약 registry, GitHub Project 운영 기준

loaring-product-ops
  - loaring-product를 조회하고 작업을 보조하는 Codex 플러그인

loaring-backend
  - product의 확정 Story/API 계약을 기준으로 provider 구현

loaring-frontend
  - product의 확정 Story/API 계약을 기준으로 consumer 구현
```

`loaring-product-ops`는 `loaring-product`, `loaring-backend`, `loaring-frontend` 안에 복사하지 않는다. 팀원은 Codex 환경에 플러그인으로 설치해서 사용한다.

## 설치

팀원 런타임 기준:

- Python `3.11`
- `uv`
- project metadata의 `requires-python = ">=3.11,<3.12"`
- MCP runtime dependency는 `uv sync`로 설치한다.

팀원 배포는 이 저장소를 team marketplace root로 등록하는 방식을 기본으로 한다.

```txt
project_plugin/
  .agents/
    plugins/
      marketplace.json
  .codex-plugin/
    plugin.json
  skills/
  mcp/
```

`.agents/plugins/marketplace.json`:

```json
{
  "name": "loaring",
  "interface": {
    "displayName": "LoaRing"
  },
  "plugins": [
    {
      "name": "loaring-product-ops",
      "source": {
        "source": "local",
        "path": "."
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

팀원 설치:

```bash
git clone https://github.com/xonme888/project_plugin.git
cd project_plugin
codex plugin marketplace add .
codex plugin add loaring-product-ops@loaring
```

플러그인 소스 검증 또는 로컬 MCP 실행 전에는 저장소 root에서 의존성을 맞춘다.

```bash
uv sync
```

업데이트 후 팀원은 marketplace 저장소에서 `git pull`을 실행한 뒤 같은 `codex plugin add ...` 명령을 다시 실행한다. Codex가 새 skill과 MCP 도구를 읽도록 새 task에서 테스트한다.

## 노출 스킬

| Skill | 책임 |
|------|------|
| `story-intake` | Story 초안, Project 필드 후보, backlog 정리 |
| `requirement-analysis` | 요구사항 분류, 기존 Story/API 중복 확인, API 영향 분석 |
| `api-contract` | API spec 작성/변경, registry 조회, 공통 규칙, breaking change 판단 |
| `implementation-brief` | product 계약을 provider/consumer/QA 작업 지시서로 변환 |

계약 조회, 공통 에러코드, 명명규칙, response envelope, 변경 분류는 별도 스킬로 노출하지 않고 `api-contract` 내부 절차로 처리한다.

## 사용 원칙

- `loaring-product`가 Story, 요구사항, API 계약의 단일 원본이다.
- 구현 저장소는 product 문서를 vendoring하지 않는다.
- Backend와 frontend는 서로의 저장소를 직접 읽거나 수정하지 않는다.
- 구현 중 계약 변경이 필요하면 product Story 또는 product PR에 질문/결정 이력을 남긴다.
- GitHub Issue, PR, Project 변경은 사용자가 명시적으로 승인한 외부 action만 수행한다.
- 팀별 구현 skill은 각 구현 저장소에서 관리한다.

## GitHub 계약 조회

`gh` 인증이 되어 있으면 product repo를 clone하지 않고 계약 파일을 조회할 수 있다.

```bash
uv run python scripts/fetch_product_contract.py
uv run python scripts/fetch_product_contract.py --path docs/api/212-auth-signup-login.api-spec.json
uv run python scripts/fetch_product_contract.py --ref docs/123-auth-contract
```

기본 조회 대상은 `loaring-story/loaring-product@develop`이다.

## MCP와 로컬 캐시

패키징된 플러그인은 FastMCP 기반 MCP 서버를 통해 `loaring-product` 조회를 캡슐화한다. Backend나 frontend 저장소에서 플러그인을 실행하는 사용자는 product 저장소 구조를 직접 알 필요 없이 Story/API 계약 메타데이터를 조회할 수 있다.

로컬 sqlite 캐시는 기본적으로 `~/.codex/loaring-product-ops/loaring-product-ops.sqlite`에 저장한다. 이 캐시는 조회 성능, 검색, readiness 점검을 위한 보조 데이터이며 Story/API 계약의 원본이 아니다. 승인된 Story, API spec, registry, Project 결정의 source of truth는 계속 `loaring-product`다.

MCP 도구는 기본적으로 조회/계획을 먼저 반환한다. GitHub Project 필드 수정, Issue comment 게시, 브랜치 생성처럼 외부 상태를 바꾸는 도구는 `apply=true`와 `confirm=true`가 모두 있어야 실행된다.

- `loaring_sync_product`: product docs를 sqlite에 동기화
- `loaring_find_story`: 요구사항, Story map, API catalog 캐시 검색
- `loaring_get_contract`: Story 또는 requirement에 연결된 API 계약 메타데이터 조회
- `loaring_validate_contract_readiness`: backend/frontend 구현 착수 가능한 API 계약 준비 상태 점검
- `loaring_infer_project_fields`: Story/API 문서 기준으로 `Contract Required`, `Contract Readiness`, `Implementation Target` 권장값 계산
- `loaring_sync_stories`: GitHub Story Issue를 sqlite에 동기화
- `loaring_sync_project`: GitHub Project 필드값을 sqlite에 동기화
- `loaring_sync_github`: Story Issue와 Project 필드값을 함께 동기화
- `loaring_get_story`: Story Issue와 Project 필드값 조회
- `loaring_find_cached_stories`: 캐시된 Story Issue 제목/본문 검색
- `loaring_migration_dry_run`: legacy Story Issue를 `loaring-product`로 옮기기 전 read-only 마이그레이션 계획 생성
- `loaring_plan_story_work`: Story의 Status, 계약 상태, target을 기준으로 다음 액션과 브랜치 후보 계산
- `loaring_prepare_branch`: Story 번호와 target으로 표준 브랜치명과 git 명령 생성
- `loaring_validate_workflow`: Project Story들의 필드 누락, 계약 상태 불일치, Status 리스크 점검. `sprint`를 생략하면 GitHub Project의 현재 Sprint iteration을 기준으로 조회하고, `assignee`로 GitHub login 담당자 필터를 걸 수 있다.
- `loaring_update_project_fields`: MCP 추론값이나 명시 필드값을 GitHub Project에 반영할 변경 계획 생성 또는 승인 기반 적용
- `loaring_sync_contract_readiness_options`: Project의 `Contract Readiness` 옵션을 표준값과 비교하고 승인 시 보정
- `loaring_apply_workflow_transition`: 계약 gate를 확인한 뒤 `Status` 전이 계획 생성 또는 승인 기반 적용
- `loaring_create_work_branch`: 표준 Story 브랜치를 계획하거나 승인 시 `git switch -c` 실행
- `loaring_validate_branch_name`: 현재 또는 지정된 브랜치명이 Story/target 규칙과 맞는지 검사
- `loaring_prepare_pr`: Story, target, 계약 상태 기준으로 PR 제목/본문 초안 생성
- `loaring_link_pr_to_project`: PR 본문에 `Related #...` 연결이 있는지 확인하고 승인 시 Story를 `In Request`로 전이
- `loaring_sprint_report`: Sprint별 Status, readiness, target, blocker 요약. `sprint`를 생략하면 GitHub Project의 현재 Sprint iteration을 기준으로 조회하고, `assignee`로 GitHub login 담당자 필터를 걸 수 있다.
- `loaring_contract_gap_report`: `Contract Required=Yes`인데 readiness가 `Missing`, `Draft`, `Blocked`인 Story 목록. `sprint` 생략 시 현재 Project Sprint, `assignee` 지정 시 해당 담당자 Story만 조회한다.
- `loaring_create_api_contract_issue_comment`: `[계약 질문]`, `[계약 결정]` 댓글 본문 생성 또는 승인 기반 게시

PR 생성 자체는 아직 수행하지 않는다. `loaring_prepare_pr`은 제목/본문 초안을 만들고, 실제 PR 생성은 별도 승인 기반 GitHub 작업으로 둔다.

GitHub Project v2 필드 조회에는 `gh` 토큰의 `read:project` scope가 필요하다. 해당 scope가 없으면 Project 동기화는 실패로 중단하지 않고 `blocked` 상태와 필요한 scope를 반환한다.

Story Issue는 마이그레이션 중에도 기본적으로 `loaring-story/loaring-product`를 조회한다. 과거 Story가 `loaring-story/loaring-sotry`에 남아 있는 경우 `--include-legacy` 또는 MCP `includeLegacy: true`로 legacy repo를 read-only 보강 조회할 수 있다. 새 Story, 새 계약, Project 운영의 기준은 `loaring-product`다.

## Workflow 도구

표준 브랜치 규칙:

- Product/API 계약: `docs/{story-id}-{slug}-contract`
- Backend: `be/{story-id}-{slug}`
- Frontend: `fe/{story-id}-{slug}`
- Fix: `fix/{issue-id}-{slug}`
- 일반 문서/운영: `docs/{slug}` 또는 `chore/{slug}`

`loaring_plan_story_work`는 캐시된 Story, Project 필드, API 계약 연결을 함께 읽어 다음 액션을 계산한다. API 계약이 `Missing`인 Story는 backend/frontend 구현 시작 전 `api-contract`로 넘기고, `Backend Ready`인 Story는 backend 브랜치만, `Frontend Ready`인 Story는 frontend 브랜치만, `Ready`인 Story는 양쪽 브랜치 후보를 반환한다.

`loaring_validate_workflow`는 Sprint 단위 점검에 사용한다. 예를 들어 `sprint: "sprint 3"`으로 호출하면 해당 Sprint Story만 대상으로 필수 Project 필드, MCP 추론값과 실제 필드값 불일치, 계약 없이 구현 상태로 넘어간 Story를 점검한다. `sprint`를 넘기지 않으면 GitHub Project의 `Sprint` iteration 설정에서 현재 날짜가 포함된 iteration title을 계산해 그 Sprint만 조회한다. `assignee: "github-login"`을 함께 넘기면 해당 담당자 Story만 남긴다.

Status 전이 규칙:

- 계약 또는 product 정리 시작: `start-contract`, `start-product` -> `In Progress`
- backend 구현 시작: `start-backend` -> `In Progress`, 단 `Contract Required=Yes`이면 `Backend Ready` 또는 `Ready` 필요
- frontend 구현 시작: `start-frontend` -> `In Progress`, 단 `Contract Required=Yes`이면 `Frontend Ready` 또는 `Ready` 필요
- PR 생성/리뷰 요청: `request-review` -> `In Request`, 단 readiness가 `Missing`, `Draft`, `Blocked`이면 차단
- QA 통과/완료: `qa-pass`, `complete` -> `Done`, target별 완료 가능한 readiness 필요

Contract Readiness 값:

- `Not Required`: API 계약이 필요 없는 Story
- `Missing`: API 계약이 필요하지만 연결된 full api-spec이 없음
- `Draft`: 계약 초안은 있으나 backend/frontend 구현 착수 기준이 아직 부족함
- `Backend Ready`: API provider인 backend가 구현 시작 가능한 상태
- `Frontend Ready`: API consumer인 frontend가 구현 시작 가능한 상태
- `Ready`: backend와 frontend 모두 구현 시작 가능한 상태
- `Blocked`: 권한, 응답, 에러, API 분리 등 계약 결정이 막힌 상태

마이그레이션 전에는 먼저 드라이런 리포트를 만든다.

```bash
uv run python scripts/migration_dry_run.py
```

이 스크립트는 product docs와 legacy Issue를 조회하지만 GitHub에는 쓰지 않는다. 실제 Issue 생성, Project 필드 복원, `traceability.yml`/`api-catalog.yml` 갱신은 별도 승인 기반 단계로 진행한다.

드라이런 리포트에서 `create-in-product`는 아직 product repo에서 매칭되는 Story Issue를 찾지 못했다는 뜻이다. `linkedRequirements`와 `linkedApiSpecs`가 있는 항목은 product 문서가 이미 legacy Issue 번호를 참조하고 있으므로, 실제 마이그레이션 후 새 product Issue 번호로 연결 파일을 갱신해야 한다.

## 독립성 점검

```bash
uv run python scripts/audit_independence.py /path/to/loaring-product /path/to/loaring-backend /path/to/loaring-frontend
```

이 검증은 각 저장소 문서에 monorepo 전제나 상대 경로 결합이 남아 있는지 확인한다.

## 릴리즈 점검

팀에 배포하기 전에 기본 검증을 실행한다.

```bash
uv run python scripts/validate_release.py
uv run --with pyyaml python /path/to/plugin-creator/scripts/validate_plugin.py .
```

`validate_release.py`는 다음을 확인한다.

- 필수 plugin 파일 존재 여부
- `.codex-plugin/plugin.json` 기본 필드
- Python `3.11` runtime과 `requires-python = ">=3.11,<3.12"` 정책
- FastMCP dependency import 가능 여부
- MCP `tools/list` 응답, schema/handler 일치, 대표 `tools/call`
- Python compile 가능 여부
- 대표적인 token, secret, API key 패턴 포함 여부

이 저장소에는 GitHub token이나 OpenAI key를 저장하지 않는다. GitHub 접근은 설치한 사용자의 `gh` 인증과 권한을 사용한다.

## 라이선스

MIT License. 자세한 내용은 `LICENSE`를 참고한다.
