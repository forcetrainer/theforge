# Phase 5 — Runner Commit Discipline Implementation Plan

> **For agentic workers:** Execute task-by-task following the Execution section
> of the planning skill, with strict TDD per task. Checkboxes track progress.

**Goal:** The Codex runner commits each passed task and refuses a dirty tree, so the plan-level final review diffs exactly this plan's work instead of the whole uncommitted working tree.
**Architecture:** All runner behavior lives in `scripts/forge-run.py` (Python stdlib, git via subprocess). Commit discipline is a clean-tree precondition at invocation start, a commit after each passed task, a per-task review base of the prior commit, and a `base_commit` persisted in `run.json` for the whole-plan final diff. Two doc/rule edits (shared planning skill, user-facing docs) accompany the code.
**Tech stack:** Python 3 stdlib, `subprocess` to `git`, `pytest`.
**Global Constraints:** stdlib only, no new dependencies; `.forge/` stays self-ignored and is never staged; Claude Code execution path unchanged; every runner behavior change carries a test in `tests/test_forge_run.py` using a real temporary git repo.

### Task 1: Runner commit discipline
- [x] Done — passed (1 review finding fixed: git add -A now fails loud)

**Files:**
- Modify: `scripts/forge-run.py` (add clean-tree precondition, per-task commit, per-task base = prior commit, persisted `base_commit`; retire `_snapshot_worktree`)
- Test: `tests/test_forge_run.py` (new cases on a real temp git repo)

**Spec:** Commit discipline, Task loop, Receipts, Resume, Halt

**Interface:**
- `_working_tree_dirty(cwd)` → `list[str] | None`: `git status --porcelain` lines (dirty paths); `[]` when clean; `None` when `cwd` is not a git repo. The self-ignored `.forge/` never appears (its `*` gitignore).
- `_git_commit_task(cwd, task)` → `str | None`: `git add -A` then commit `forge: task <N> — <title>`; returns the new HEAD SHA, or `None` when nothing was staged (empty `git diff --cached`) or `cwd` is not a git repo. Never commits when the stage is empty.
- `_read_base_commit(run_dir)` → `str | None`: the `base_commit` field from an existing `run.json` in `run_dir`, else `None`.
- `write_run_json(run_dir, plan_path, spec_path, status, task_summaries, base_commit)`: gains a trailing `base_commit` parameter, written as a top-level field.
- Each entry in `task_summaries` gains a `commit` key (the task's commit SHA, or `None` when skipped-empty).
- `_snapshot_worktree` is removed; `execute_task`'s per-task review base becomes `_git_head(cwd)` captured at task start (the prior task's commit; run-start commit for task 1).
- Wiring in `run_plan`: (1) before creating the run dir or `.forge/` gitignore, if `_working_tree_dirty(cwd)` is a non-empty list, raise `RuntimeError` naming the dirty paths (→ contract error exit 1); a `None` (non-repo) result skips the precondition. (2) `base_commit = _read_base_commit(run_dir) or _git_head(cwd)`, computed once at start. (3) after a task returns `passed` and `annotate_ledger` runs, call `_git_commit_task` and store the returned SHA in that task's summary. (4) the final review diffs `base_commit` (not a freshly recaptured HEAD). (5) pass `base_commit` to `write_run_json`.

**Tests:**
- Dirty tracked file at invocation start → contract error (exit 1) naming the path, on a first run.
- Dirty tree at invocation start → contract error on a resume (run-dir with prior receipts) too.
- Clean start, one task passes → exactly one new commit whose message is `forge: task 1 — <title>`.
- Two passed tasks → one commit each; HEAD advances by two; each commit holds only its task's changes.
- Escalated task (forced findings past the rework cap) → no commit created; HEAD unchanged from the last passed task.
- Per-task review base is the prior commit: the review packet for task N contains only task N's diff, not an earlier task's.
- `base_commit` is written to `run.json` on the first invocation (HEAD before any task commits).
- Resume reuses the persisted `base_commit`: after early tasks have committed (HEAD moved), the final review still diffs from the original `base_commit`, spanning the whole plan.
- A passed task that changes no files → commit skipped, its summary `commit` is `None`, and `git log` gains no empty commit.
- No remaining reference to `_snapshot_worktree` anywhere in `scripts/` or `tests/`.

**Acceptance:**
- `python -m pytest tests/test_forge_run.py -q` passes.
- `python -m pytest -q` (full suite) passes.

**Tier:** complex.

**Depends on:** nothing.

### Task 2: Env-gated-skip authoring rule
- [x] Done — passed

**Files:**
- Modify: `skills/planning/SKILL.md` (acceptance-command authoring rule)

**Interface:** Add to the `**Acceptance:**` field guidance in the Task structure section a rule stating: an environment-gated skip is not a pass — an acceptance command must assert the required infrastructure is present, or make the skip exit non-zero. Harness-neutral (binds both Codex and Claude paths).

**Tests:** none (prose rule; verified by acceptance grep).

**Acceptance:**
- `grep -qi "skip" skills/planning/SKILL.md` and the added sentence states skip-is-not-a-pass near the `**Acceptance:**` field.

**Tier:** trivial.

**Depends on:** nothing.

### Task 3: Runner docs — precondition, commits, resume
- [x] Done — passed

**Files:**
- Modify: `README.md` (Codex runner section: clean-tree precondition + per-task commit behavior)
- Modify: `skills/planning/codex-execution.md` (clean-tree precondition, per-task commits, commit-or-discard-before-resume ergonomic)

**Spec:** Commit discipline, Resume, Retirements / doc changes

**Interface:** Prose only, derived from the spec's Commit discipline section. README states the runner requires a clean working tree at start and commits each passed task as `forge: task N — <title>`. `codex-execution.md` states the same precondition, per-task commits, and that on resume the human must commit (as a fix) or discard an escalated task's uncommitted attempt before re-invoking.

**Tests:** none (prose; verified by acceptance grep).

**Acceptance:**
- `grep -qi "clean working tree" README.md`
- `grep -qi "clean" skills/planning/codex-execution.md` and `grep -qi "discard" skills/planning/codex-execution.md` (the precondition and the commit-or-discard resume ergonomic both present).

**Tier:** trivial.

**Depends on:** nothing.
