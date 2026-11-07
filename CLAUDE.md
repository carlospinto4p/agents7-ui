# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Core Rules

1. **Self-Improvement**: When the user corrects a mistake, ALWAYS update the
   relevant guidelines (`.claude/rules/` or this file) to prevent it from
   happening again.
2. **Keep CLAUDE.md Minimal**: Do not include library schemas, architecture
   details, or information discoverable from the codebase. Keep only
   essential rules and commands here.
3. **Periodic Reviews**: Triggered by backlog depth — when `/backlog` shows
   fewer than 5 open items, propose `/scan`, `/improvements`, and `/prune`
   together.

## Project Overview

The web UI for the `agents7` framework: a FastAPI backend (`backend/`)
and a Svelte (Vite) frontend (`frontend/`). The framework is a tagged
release from its own repository (`github.com/carlospinto4p/agents7`),
pinned in `backend/pyproject.toml` and `Dockerfile.backend`. On the
owner's machine the repositories sit side by side in one `agents7/`
folder, this one as `ui/`.

## Shell Commands

Never use compound shell commands with `cd && git` or `cd &&` chaining.
Always use separate commands or `cd` first, then run the git/shell command
independently.

## Project Configuration

Store project rules and preferences in project config files (e.g.,
`.claude/settings.json`, `CLAUDE.md`), NOT in memory files. Never save
user instructions as memory files.

## Common Commands

**IMPORTANT**: Always use `uv run` to execute Python commands. Never run
raw `python` commands. The frontend uses `pnpm` through corepack.

```bash
# Backend: install, test
uv sync --project backend
uv run --project backend pytest backend/tests/ -v

# Frontend: install, build, browser tests (Playwright, API stubbed)
corepack pnpm --dir frontend install
corepack pnpm --dir frontend run build
corepack pnpm --dir frontend run test:e2e
```

## Versioning / Release

The version lives in `backend/pyproject.toml`; the changelog is
`changelog.md`. After version bumps, always stage and commit
`backend/uv.lock` along with the version change. Never forget the lock
file.

## Testing

After any code change, run the full test suite and fix all failures before
committing: the backend tests, the frontend build and the browser tests.
Pay special attention to mock patching paths,
fixture values, and assertion text that may need updating after
refactors.

## Code Style

- Line length: 78 characters (enforced by ruff, `ruff.toml`)
- Linter: ruff
- Type hints required
- Docstring style: Sphinx/reST (`:param:`, `:return:`, `:raises:`)
- In docstrings, prefer single backticks (`` `name` ``) for inline code
  references
- Use `@staticmethod` for methods that don't use `self`

## Workflow Rules

See `.claude/rules/` for detailed guidelines:
- [Committing](.claude/rules/committing.md)
- [Versioning](.claude/rules/versioning.md)
- [Testing](.claude/rules/testing.md)
- [Metrics completeness](.claude/rules/metrics-completeness.md)
