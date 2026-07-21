---
name: git-workflow
description: "Guide LoaRing Git work from status review through staging, validation, commit, and push. Use when committing, pushing, staging, creating branches, preparing PRs, checking dirty worktrees, or deciding whether Git commands are safe."
---

# Git Workflow

Use this skill for repository state changes and Git coordination. Keep user changes separate from Codex changes unless the user explicitly asks to include them.

## Baseline

1. Run `git status --short --branch` before staging, committing, switching branches, rebasing, or pushing.
2. Inspect relevant diffs before staging. Use `git diff -- <path>` and `git diff --cached`.
3. Treat pre-existing modified files as user work. Do not revert, overwrite, or stage unrelated user changes.
4. If a file contains both user changes and Codex changes, stage only the intended hunks. Prefer a narrow cached patch when interactive staging is awkward.
5. Keep generated cache files, local databases, editor files, and build output out of commits unless the repo explicitly tracks them.

## Validation

Before committing, run the smallest validator that matches the changed surface:

- Commit message policy: `uv run python scripts/validate_commit_message.py --message "<message>"`
- Plugin release surface: `uv run python scripts/validate_release.py`
- Python tests when logic changes: `uv run python -m pytest`

If validation cannot run because of sandbox, dependency, or credential limits, state that clearly and use the approved escalation flow when the command is necessary.

## Commit

Use the `commit-message` skill for the final commit title.

Default shape:

```txt
<type>(<scope>): <Korean summary>
```

Commit only after checking:

- `git diff --cached --name-status`
- `git diff --cached` for risky or mixed files
- The commit message passes `scripts/validate_commit_message.py`

Do not amend, squash, or rewrite commits unless the user asks for history editing.

## Push

Push only when the user asks to push or when push is part of the explicit task.

Before pushing:

1. Confirm the current branch with `git status --short --branch`.
2. Confirm the target remote and branch, usually `origin develop` for this plugin.
3. Avoid pushing unrelated local commits that were not part of the current task. If the branch contains unexpected unpushed commits, summarize them before pushing.

Normal push:

```bash
git push origin <branch>
```

Do not use `--force` or `--force-with-lease` unless the user explicitly requests it for a known history-rewrite case.

## High-Risk Commands

Require explicit user request before running commands that can destroy, rewrite, or discard work:

- `git reset --hard`
- `git clean`
- `git checkout -- <path>`
- `git restore <path>`
- `git rebase`
- `git commit --amend`
- `git push --force`
- `rm` for tracked source files

When a safer read-only command can answer the question, use that first.

## Branch And PR Flow

Use existing LoaRing branch conventions when a task needs a new branch:

- Product/API contract: `docs/{story-id}-{slug}-contract`
- Backend: `be/{story-id}-{slug}`
- Frontend: `fe/{story-id}-{slug}`
- Fix: `fix/{issue-id}-{slug}`
- General docs or ops: `docs/{slug}` or `chore/{slug}`

Prefer draft PRs for early coordination when product docs or contracts can affect backend/frontend work. Do not create PRs, edit GitHub Issues, or change GitHub Project fields without explicit user approval.
