---
name: fix-errors
version: 1.0.0
description: Triage the agents7 UI backend's file-based error AND warning logs (logs/errors/, logs/warnings/) — read every record, group by root cause, fix actionable bugs with regression tests, classify the rest (by-design / external-transient), then delete the resolved log files. Use when the session-start container-log check reports unresolved logs, or when asked to fix/clear the error and warning logs.
---

<!-- opencode counterpart: .opencode/command/fix-errors.md — the
     `/fix-errors` slash shim (skills aren't `/` commands in the
     opencode TUI). Keep the two in sync. -->

Consume the agents7 UI backend's file-based logs:
**read → diagnose → fix → delete**. Despite the name, this skill
covers **both** `logs/errors/` and `logs/warnings/` — warnings are
where over-strict guards and ungraceful edge cases surface, and many
are real bugs, not harmless spam.

## When to run

- The `SessionStart` container-log check reports
  `⚠ Unresolved container logs` (non-empty files in `logs/errors/`
  or `logs/warnings/`).
- The user asks to fix, triage, or clear the error/warning logs.

## Where the logs live

The first-party **`backend`** service (`backend`) writes
level-segregated, one-file-per-process-start logs. The root is
resolved by `backend/logging_setup.py::_logs_root()`:

- **Compose stack** — `LOGS_DIR=/app` → `/app/logs`, bind-mounted to
  the host at `logs/`.
- **Local runs** (no `LOGS_DIR`) — falls back to
  `backend/logs/`.

Check **both** trees:

```
logs/          # compose runs (bind-mounted)
backend/logs/  # local, non-docker runs
  errors/                 #   ERROR + CRITICAL records
  warnings/               #   WARNING records only
```

Each line is plain text (stdlib `Formatter`, UTC), not JSON:

```
2026.06.14 12:22:06 | WARNING-routers.eval: agent.act() failed (...): boom
```

i.e. `<UTC timestamp> | <LEVEL>-<logger>: <message>`. Multi-line
records (e.g. a YAML parse error, a traceback) continue on indented
follow-on lines. Files use `delay=True`, so a file exists only once a
record was written — a non-empty file means real records to triage.
First-party loggers are `routers.*` (`routers.eval`, `routers.engine`,
`routers.catalog`, `routers.chat`, `routers.run`), the `agents7`
framework logger, and `uvicorn.error`.

## Step 1 — Read and group by root cause

Read every non-empty file in **both** folders across **both** log
roots. Do not eyeball a few and guess — parse them and group by root
cause so you act on the distinct *causes*, not the record count. Use
`uv run python` for any parsing (never raw `python`). Example summary
pass over the warnings:

```bash
cat backend/logs/warnings/*.log logs/warnings/*.log \
  2>/dev/null | uv run python -c "
import sys, re, collections
c = collections.Counter()
for l in sys.stdin:
    m = re.match(r'.*? \| (\w+)-([\w.]+): (.*)', l)
    if m:
        c[(m.group(2), m.group(3)[:70])] += 1
for (logger, msg), n in c.most_common():
    print(f'{n:4d}  {logger:20s} {msg}')
"
```

Drill into a representative full record (including any indented
follow-on lines / traceback) for each distinct cause — the truncated
message often hides the real signal.

## Step 2 — Classify each cause into exactly one bucket

Every distinct cause is one of three. "Noted but left alone" is not an
outcome.

1. **Real bug — FIX IT.** A defect in code we own: an over-strict
   guard, a missing handler, a concurrency error, an ungraceful edge
   case — **or test runs polluting the committed `logs/` tree**
   (importing `main` runs `configure_logging()` as a side effect;
   tests must redirect `LOGS_DIR` to a tmp path). Diagnose against the
   source, fix it, and **add a regression test that fails without the
   fix** (bug fixes always get a test).
2. **By-design / expected.** An intentional informational warning. No
   code change. Many warnings live here — a router that *correctly*
   logs a `WARNING` when a downstream call fails is working as
   designed. Do not turn an expected warning into a bug hunt.
3. **External / transient.** A failure outside our code with no code
   defect: Ollama unreachable (`Connection refused` to `:11434`),
   read timeouts, a remote 5xx. Logging it is correct behavior; there
   is nothing to fix.

If a "transient" cause is actually *recurring and frequent*, treat the
volume itself as the bug — the handler is too noisy or the operation
should back off. Reclassify it to bucket 1.

**Watch for test-generated records.** Messages containing `boom`,
paths under `/tmp/pytest-of-...`, or `Connection refused` to a
provider that isn't running are almost always emitted by the unit
suite exercising error paths. The individual warnings are by-design
(bucket 2), but their *presence in the committed log tree* is a
bucket-1 test-isolation bug — fix the isolation, not the router.

## Step 3 — Fix the real bugs

For each bucket-1 cause:

1. Trace the root cause to the source (the logger field names the
   module, e.g. `routers.engine`, `uvicorn.error`).
2. Apply the **generic** fix, not a patch for the one logged input
   (prefer the general case).
3. Add a regression test; confirm it fails on the unfixed code and
   passes with the fix.
4. Run the unit suite from `backend/`:
   `uv run pytest tests/ -v`.
5. Bump the version (`backend/pyproject.toml`), add a
   changelog entry (`changelog.md`), and commit per
   `.claude/rules/committing.md` (one fix per version).

## Step 4 — Delete the resolved logs (and ONLY those)

After the fixes are committed, delete the log files whose causes are
now **resolved or non-actionable** (bucket 1 fixed, 2 expected, 3
external). Keep any file holding a cause you could not resolve this
session (and backlog it).

**Ownership gotcha.** Local-run files are host-user-owned and a plain
`rm` works. Compose-run files under `logs/` may be
`root:root` (the container runs as root); if a host `rm` fails with a
permission error, delete them through a throwaway root container over
the same bind mount:

```bash
docker run --rm -v "$PWD/logs:/logs" busybox \
  sh -c 'rm -f /logs/errors/*.log /logs/warnings/*.log'
```

Confirm both folders in both roots are empty afterwards so the next
session's `SessionStart` check is quiet.

## Step 5 — Report

Summarize: the distinct causes found,
which were real bugs (with the version each fix shipped in), which
were by-design or external, what was cleared, and anything left
unresolved and backlogged.
