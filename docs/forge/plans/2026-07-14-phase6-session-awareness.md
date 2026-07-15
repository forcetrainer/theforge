# Codex Runner Session Awareness Implementation Plan

> **For agentic workers:** Execute task-by-task following the Execution section
> of the planning skill, with strict TDD per task. Checkboxes track progress.

**Goal:** Give the Codex runner session awareness — `--notify` push on terminal events, `--status` read mode, incremental `run.json`, and a Codex-only `UserPromptSubmit` hook — so a backgrounded run is never blind.
**Architecture:** A new `scripts/forge_status.py` reads `run.json` + receipts and renders both the `--status` output and the hook block; `forge-run.py` gains `--status`/`--notify` and writes `run.json` incrementally; `hooks/user-prompt-submit` (Python stdlib) imports the reader and is wired Codex-only via `~/.codex/`. Docs follow code.
**Tech stack:** Python 3 stdlib only; pytest; `osascript` (macOS notification default).
**Global Constraints:** No third-party dependencies. Codex-only — Claude Code untouched; the shared `hooks/hooks.json` gains no `UserPromptSubmit` entry. Fail loud naming the cause (DECISIONS 2026-07-11). The hook reads files only — no subprocess, no runner invocation — and must never block a prompt (any read error → silent exit 0).

### Task 1: forge_status.py — run-state reader and renderers
- [x] Done

**Files:**
- Create: `scripts/forge_status.py`
- Test: `tests/test_forge_status.py`

**Spec:** Session awareness, Receipts

**Interface:**
- `read_run_state(run_dir) -> dict | None`: parse `run.json` + the latest per-task receipts under `run_dir`; `None` when the dir is absent or holds no `run.json` and no receipts. Returned dict: `{"run_dir": str, "state": "running"|"completed"|"halted"|"contract-error", "reason": str|None, "latest_mtime": float, "tasks": [{"number": int, "status": str, "attempts": int, "finding": str|None}, ...]}`.
- State mapping from `run.json` `status`: `running`→`running`; `passed`→`completed`; `escalated`|`escalated-final-review`→`halted`; `contract-error`→`contract-error`. No `run.json` but receipts present → `running`. `reason`: halted → `task <N> escalated` for the first escalated task (or `final review escalated` for `escalated-final-review`); contract-error → the `run.json` `contract_error` message. `finding`: first outstanding finding of an escalated task, truncated to ~100 chars.
- `render_status(state) -> str`: header `run <dir>: RUNNING|COMPLETED|HALTED|CONTRACT-ERROR` with ` — <reason>` appended when halted/contract-error, then one line per task: `task <N>: <status>, attempts <X>` with ` — <finding>` appended for an escalated task. A halted run must never render indistinguishable from a completed one.
- `render_hook_block(state, now, max_lines=6, age_cutoff_h=12) -> str | None`: ≤ `max_lines` lines (run dir, overall state, per-task summary with consecutive same-status tasks range-compressed e.g. `tasks 1-4: passed`, halt reason when halted); `None` when the run is terminal (not `running`) and `now - state["latest_mtime"] > age_cutoff_h*3600`.

**Tests:** `read_run_state` returns None for a missing dir and for an empty dir; maps each `run.json` status to the right state; infers `running` from receipts-only; extracts the halt reason and truncated finding for an escalated task; `render_status` shows distinct headers for running/completed/halted/contract-error and appends the finding on an escalated task line; `render_hook_block` range-compresses consecutive same-status tasks, caps at 6 lines, returns None for a terminal run past the age cutoff, and returns a block for a terminal run within the cutoff and for any running run.

**Acceptance:** `python3 -m pytest tests/test_forge_status.py -q` passes.

**Tier:** standard

**Depends on:** nothing.

### Task 2: forge-run.py — --status mode and incremental run.json
- [x] Done

**Files:**
- Modify: `scripts/forge-run.py` (argparse `--status`; write `run.json` incrementally; re-export `forge_status`)
- Test: `tests/test_forge_status.py` (extend)

**Spec:** Runner, Receipts, Halt / escalation

**Interface:**
- `--status` flag (requires `--run-dir`): read-only branch in `main()` before any `run_plan` — call `forge_status.read_run_state` + `render_status`, print, return 0; dispatch nothing. `read_run_state` None → print `no run at DIR`, return 0. Plan/spec args not required in this mode (argparse `plan`/`--spec` become optional when `--status` is present; their absence outside `--status` still errors).
- Incremental `run.json`: `write_run_json` is called with `status="running"` immediately after the clean-tree check (persisting `base_commit`, `tasks=[]`), rewritten after each task with the accumulated summaries (still `status="running"`), and rewritten once more at the end with the terminal status (existing final call). Resume still reads `base_commit` from the first-invocation `run.json`.
- Contract-error persistence: `main()` catches the `RuntimeError` from `run_plan`; when `run_dir` exists, write `run.json` with `status="contract-error"` and a `contract_error` message field (via `write_run_json` extended to accept/thread an optional `contract_error`), then exit 1 as today. Errors before `run_dir` exists write nothing (dirty tree, unparseable plan) — stderr only.
- Stdout narrative: `run_plan`/`execute_task` print one human-readable progress line per task to stdout (task started, attempt N, verdict) for `tail -f` on a redirected log — never load-bearing (state lives in receipts/`run.json`); `--status` and the hook never read stdout.

**Tests:** `--status` on a running/completed/halted/contract-error fixture run-dir prints the mapped header and per-task lines and exits 0; `--status` on a nonexistent dir prints `no run at DIR`, exit 0; `--status` dispatches nothing (fake-codex argv log stays empty); a normal run writes `run.json` `status="running"` before the first task and a terminal status at the end (assert an intermediate read shows `running`); a contract error after the run-dir exists (e.g. unparseable reviewer verdict) leaves `run.json` `status="contract-error"` with the message; a dirty-tree contract error writes no `run.json`.

**Acceptance:** `python3 -m pytest tests/test_forge_status.py -q` passes; `python3 -m pytest -q` passes; `python3 scripts/forge-run.py --status --run-dir /nonexistent` exits 0.

**Tier:** standard

**Depends on:** Task 1.

### Task 3: forge-run.py — --notify on terminal events
- [x] Done

**Files:**
- Modify: `scripts/forge-run.py` (argparse `--notify`; `fire_notify`; three call sites)
- Test: `tests/test_forge_notify.py`

**Spec:** Session awareness, Halt / escalation

**Interface:**
- `fire_notify(event, summary, cmd=None)`: `event` in `escalated`|`contract-error`|`completed`. Fired via `subprocess.Popen`, fire-and-forget — wrapped so any failure is a stderr warning, never raised, never changes the exit code. `cmd` given (a string) → `Popen(shlex.split(cmd) + [event, summary])`. `cmd` None → on `sys.platform == "darwin"`: `Popen(["osascript", "-e", 'display alert "<summary>"'])`; otherwise write the summary line to stderr and fire nothing.
- `--notify CMD` argparse arg (string, default None), threaded into `run_plan(..., notify_cmd=None)`.
- Call sites, exactly one notify per terminal event: `run_plan` fires `escalated` at the escalation break (summary = `task <N> escalated: <one-liner>`) and `completed` at successful end (summary = `<K> tasks passed`); `main()` fires `contract-error` in the `RuntimeError` except path (summary = the cause). Final-review escalation fires `escalated` as well.

**Tests:** each terminal event fires the notifier exactly once with `event` and `summary` as the trailing argv (a fake notifier script records its argv); a broken `--notify` command (nonzero/nonexistent) leaves the runner's exit code unchanged; no `--notify` on darwin resolves to an `osascript` argv (platform monkeypatched, `Popen` captured); no `--notify` off darwin writes the summary to stderr and fires nothing; escalation, completion, and contract-error each map to the correct event string.

**Acceptance:** `python3 -m pytest tests/test_forge_notify.py -q` passes; `python3 -m pytest -q` passes.

**Tier:** standard

**Depends on:** Task 2.

### Task 4: user-prompt-submit hook
- [x] Done

**Files:**
- Create: `hooks/user-prompt-submit` (executable, `#!/usr/bin/env python3`)
- Test: `tests/test_prompt_hook.py`

**Spec:** Session awareness

**Interface:**
- `hooks/user-prompt-submit`: Python stdlib executable. Reads (and ignores beyond `cwd`) the hook input JSON on stdin; resolves the runs dir as `./.forge/runs/` under the process cwd. Adds `scripts/` to `sys.path` (resolved relative to `__file__`: `../scripts`) and imports `forge_status`.
- Behavior: no `./.forge/runs/` or no run subdirs → print nothing, exit 0. Else pick the latest run dir (lexical by name), `read_run_state`, `render_hook_block(state, now=time.time())`; `None` → print nothing; else emit `{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "<block>"}}` on stdout. Any exception / malformed `run.json` → print nothing, exit 0, write a one-line note to stderr. File reads only; no subprocess; no runner invocation.
- Not wired into `hooks/hooks.json` (that fires in Claude). Codex wiring is documented install (Task 5).

**Tests:** silent (empty stdout, exit 0) when cwd has no `.forge/`; silent when the only run is terminal and past the 12h cutoff (mtime forced old); emits valid JSON with `additionalContext` ≤ 6 lines for a live-run fixture; a halted run's block includes the halt reason; a completed-recent run emits a block; malformed `run.json` → empty stdout, exit 0, stderr note. (Live firing inside a Codex session is deferred verification — recorded in the summary, not tested here.)

**Acceptance:** `python3 -m pytest tests/test_prompt_hook.py -q` passes; `python3 -m pytest -q` passes.

**Tier:** standard

**Depends on:** Task 1.

### Task 5: Docs — codex-execution.md and README
- [x] Done

**Files:**
- Modify: `skills/planning/codex-execution.md` (never-background-blind contract; `--notify`/`--status` invocation)
- Modify: `README.md` (Codex section: `--notify`/`--status`; one-time `~/.codex/config.toml` hook-install snippet)

**Spec:** Session awareness, Runner

**Interface:** codex-execution.md gains the never-background-blind rule — the runner is always backgrounded to a redirected log **with `--notify`**; on re-entry the orchestrator trusts hook-injected state or runs `--status --run-dir`, never `ps`, never memory. README Codex section documents `--notify`/`--status` and the copy-paste `[[hooks.UserPromptSubmit]]` registration for `~/.codex/config.toml` (command = `python3 <plugin-root>/hooks/user-prompt-submit`), noting it is Codex-only and gated on Codex trust. All doc claims verified against `forge-run.py`/hook behavior before writing.

**Tests:** none (prose contracts; content checked at review).

**Acceptance:** `grep -ci "notify" skills/planning/codex-execution.md` ≥ 1; `grep -c "UserPromptSubmit" README.md` ≥ 1; `python3 -m pytest -q` passes.

**Tier:** standard

**Depends on:** Task 2, Task 3, Task 4.

### Task 6: Lockstep version bump
- [x] Done

**Files:**
- Modify: `.claude-plugin/plugin.json` (version bump)
- Modify: `.codex-plugin/plugin.json` (same version)

**Interface:** minor version bump; identical version string in both files.

**Tests:** existing `tests/test_manifests.py` version-equality test covers it.

**Acceptance:** `python3 -m pytest tests/test_manifests.py -q` passes.

**Tier:** trivial

**Depends on:** Task 5.
