# Phase 2: Execution Efficiency & Scripts Implementation Plan

> **For agentic workers:** Execute task-by-task following the Execution section
> of the planning skill, with strict TDD per task. Checkboxes track progress.

**Goal:** Land the phase-2 execution-efficiency rules in the planning skill and agent files, and ship the two pipeline scripts with tests.

**Architecture:** Planning skill carries orchestrator-facing rules; agent files carry reviewer-facing rules (split by actor, per DECISIONS 2026-07-02). Two self-contained Python stdlib CLI scripts do mechanical extraction: plan/spec → worker brief, task + git diff → review packet. Spec: `docs/theforge/specs/2026-07-02-phase2-execution-efficiency-design.md`.

**Tech stack:** Markdown skills/agents; Python 3 stdlib (argparse, tempfile, subprocess, unittest); no third-party dependencies.

**Global Constraints:** Python 3 stdlib only — no pip installs, no shared module (each script self-contained, duplicated task-block parser accepted). Exactly two scripts. Any degraded-output path exits nonzero with a stderr message — never a thin brief or partial packet. Skill/agent prose passes the sentence test (requirement, contract, or decision — else cut). Script filenames, CLI flags, and output filenames exactly as specified in the Interface blocks.

**Note on `**Spec:**` lines below:** this plan uses the task-level `**Spec:**` line that Task 1 adds to the template — headings refer to sections of the phase-2 spec.

### Task 1: Planning skill — plan-time additions + Execution rewrite
- [x] Done

**Files:**
- Modify: `skills/planning/SKILL.md`

**Spec:** Planning skill — plan-time edits, Planning skill — Execution section rewrite

**Interface:** task-template line (optional, after **Files:**): `**Spec:** <section heading>, <section heading>` — heading text, unique prefix acceptable, matched case-insensitively. Script references by exact name: `scripts/extract-brief.py`, `scripts/review-packet.py`.

**Changes (all pinned by spec §1–§2):**
- Task structure template + explanation gain the `**Spec:**` line.
- File-structure/decomposition guidance gains the width rule (critical path, shared interfaces over sequence).
- **Tier** paragraph appends the tier-down preference sentence.
- Execution section: context-lifetime rule replaces the "≤3 tasks" inline threshold; file-referenced briefs via `extract-brief.py` (never pasted plan/spec content, "read these N files and spec §X, nothing else"); trivial tasks batch into one `forge-light` dispatch respecting `Depends on`; thin orchestrator (one-paragraph worker reports; diffs/packets flow reviewer↔file via `review-packet.py`); orchestrator never pre-rates severity; rework guardrails (2-iteration cap then escalate with findings; summary reports review-cycle counts per task); multi-task plans get one broad final review on `forge-deep` after all tasks pass; close-out gains the taste-miss-capture sentence.
- Unchanged: routing table, combined-review + escalation flow, proportional review, deferral rule, pre-fork-plan compatibility note.

**Tests:** prose task — no unit tests. Verification via acceptance greps.

**Acceptance:** `grep -c "≤3" skills/planning/SKILL.md` → 0; grep finds in the file: `extract-brief.py`, `review-packet.py`, `**Spec:**`, "critical path", a 2-iteration cap statement, "review-cycle counts", final-review-on-`forge-deep` statement, tier-down sentence. Read-through confirms the Unchanged list intact and sentence test holds.

**Tier:** standard

**Depends on:** nothing

### Task 2: Agent files — reviewer integrity
- [x] Done

**Files:**
- Modify: `agents/forge-standard.md` (review paragraph)
- Modify: `agents/forge-deep.md` (review paragraph)

**Spec:** Agent edits

**Changes:** both review paragraphs add: review is read-only — never modify files; "can't verify from diff" is a valid verdict, report it as such; implementer rationales never suppress a finding. `forge-deep.md` review role widens to escalation reviewer **or** final integration reviewer (whole-plan diff against spec). `agents/forge-light.md` untouched.

**Tests:** prose task — no unit tests.

**Acceptance:** grep finds "read-only" (or "never modify"), "can't verify", and a rationales-don't-suppress statement in both files; grep finds a final-integration-review statement in `forge-deep.md`; `git diff --stat` shows no change to `forge-light.md`.

**Tier:** trivial

**Depends on:** nothing

### Task 3: extract-brief.py + tests
- [x] Done

**Files:**
- Create: `scripts/extract-brief.py`
- Test: `tests/test_extract_brief.py`

**Spec:** Scripts

**Interface:**
- CLI: `extract-brief.py <plan.md> <task-number> [--spec <spec.md>] [--out <dir>]`
- Output file: `<out>/task-<N>-brief.md`; absolute path printed to stdout; `--out` defaults to a fresh `tempfile.mkdtemp()` dir.
- Brief contents, in order: plan header contracts (the `**Goal:**` and `**Global Constraints:**` lines; omit constraints when absent), full Task N block, each spec section named on the task's `**Spec:**` line.
- Task block = `### Task <N>:` heading through next `###`/`##` heading or EOF. Spec-section match = case-insensitive heading-prefix against `--spec` headings.
- Exit nonzero + stderr message on: plan unreadable, task number not found, task declares `**Spec:**` but `--spec` absent, section prefix unmatched, section prefix ambiguous (matches >1 heading).
- Exit 0 with no `**Spec:**` line on the task: brief = header + task block only (`--spec` unused).

**Tests (unittest, fixtures via tempfile):**
- extracts header + task block from a plan without `**Spec:**` lines (fixture mirrors phase-1 plan shape)
- extracts declared spec sections into the brief, in declared order
- heading match is case-insensitive and accepts a unique prefix
- ambiguous prefix exits nonzero with stderr message
- unmatched section exits nonzero
- unknown task number exits nonzero
- `**Spec:**` declared but no `--spec` flag exits nonzero
- `--out` dir honored; default out dir is writable temp; path printed to stdout
- last task in file (EOF-terminated block) extracts fully

**Acceptance:** `python3 -m unittest tests.test_extract_brief -v` all pass; `python3 scripts/extract-brief.py docs/theforge/plans/2026-07-02-phase1-pipeline-skill-edits.md 1` prints a brief path whose file contains Task 1's block; same command with task number 99 exits nonzero.

**Tier:** standard

**Depends on:** nothing

### Task 4: review-packet.py + tests
- [x] Done

**Files:**
- Create: `scripts/review-packet.py`
- Test: `tests/test_review_packet.py`

**Spec:** Scripts

**Interface:**
- CLI: `review-packet.py <plan.md> <task-number> --base <git-ref> [--out <dir>]`
- Output file: `<out>/task-<N>-review.md`; absolute path printed to stdout; `--out` defaults to a fresh `tempfile.mkdtemp()` dir.
- Packet contents, in order: full Task N block, then `git diff <base>` output (run in the plan file's repo, `cwd` = plan's directory) inside a fenced `diff` block.
- Same task-block parser contract as Task 3 (duplicated by design — Global Constraints).
- Exit nonzero + stderr message on: plan unreadable, task number not found, git exits nonzero (bad ref, not a repo) — git's stderr relayed.
- Empty diff is not an error: packet notes "no changes vs <base>".

**Tests (unittest, temp git repo fixture: init, commit, modify, commit):**
- packet contains task block and the diff between two commits
- `--base HEAD` after clean commit yields the empty-diff notice, exit 0
- bad git ref exits nonzero with git stderr relayed
- unknown task number exits nonzero
- plan outside a git repo exits nonzero
- `--out` honored; path printed to stdout

**Acceptance:** `python3 -m unittest tests.test_review_packet -v` all pass; `python3 scripts/review-packet.py docs/theforge/plans/2026-07-02-phase1-pipeline-skill-edits.md 1 --base HEAD~1` prints a packet path whose file contains a diff section.

**Tier:** standard

**Depends on:** nothing

### Task 5: Version bump + README
- [x] Done

**Files:**
- Modify: `.claude-plugin/plugin.json` (version 0.3.0 → 0.4.0)
- Modify: `README.md` (add scripts to the shipped-surface description: two pipeline scripts, one line each)

**Tests:** none.

**Acceptance:** `grep 0.4.0 .claude-plugin/plugin.json`; `grep -c "extract-brief\|review-packet" README.md` ≥ 1; `python3 -m unittest discover -s tests -v` all pass.

**Tier:** trivial

**Depends on:** Task 1, Task 2, Task 3, Task 4
