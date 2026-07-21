---
name: commit-message
description: "Prepare or review LoaRing git commit messages. Use when writing commit messages, checking commit titles, creating commit-msg hooks, or validating that commits follow the LoaRing Conventional Commit policy."
---

# Commit Message

Use this skill when the user asks for a commit message, commit review, commit policy, or commit validation.

## Format

Use Conventional Commits. Keep only the convention tokens in English:

```txt
<type>(<scope>): <summary>
```

`scope` is optional, but prefer it when the changed area is clear.
Write `summary` and body text in Korean by default. Use English only for code identifiers, API names, field names, branch names, and required footer tokens such as `BREAKING CHANGE:`.

Allowed types:

- `feat`: user-visible feature or product capability
- `fix`: bug fix
- `docs`: documentation, Story, requirement, API contract, or implementation brief
- `refactor`: behavior-preserving code structure change
- `test`: test-only change
- `chore`: repository maintenance
- `ci`: CI or automation
- `build`: dependency, package, or build configuration
- `perf`: measurable performance improvement
- `revert`: revert a previous commit

Recommended scopes:

- `story`
- `requirement`
- `api`
- `brief`
- `workflow`
- `mcp`
- `github`
- `release`
- `docs`
- `tests`

## Rules

- Keep the first line at 72 characters or less.
- Write the summary in Korean and without a trailing period.
- Use lower-case `type` and `scope`.
- Use `!` before `:` for breaking changes, for example `feat(api)!: 인증 응답 구조 변경`.
- Add a body when the reason, migration note, or product decision is not obvious from the title.
- Add `BREAKING CHANGE:` footer when the change requires coordinated migration.
- Do not include issue numbers unless they are useful to the reviewer; prefer PR bodies for detailed traceability.

## Examples

Good:

```txt
docs(api): 회원가입 계약 준비 규칙 추가
feat(mcp): Story 워크플로 전이 검증 추가
fix(github): Project 필드 수정을 승인 기반으로 유지
chore(release): 번들 스킬 메타데이터 검증 추가
```

Bad:

```txt
updated files
Fix stuff.
docs(api): add signup contract readiness rules
docs(api): 회원가입 계약 준비 규칙 추가.
```

## Validation

Run the repository validator for a proposed message:

```bash
uv run python scripts/validate_commit_message.py --message "docs(api): 회원가입 계약 준비 규칙 추가"
```

For a commit-msg hook, pass the commit message file:

```bash
uv run python scripts/validate_commit_message.py --file "$1"
```
