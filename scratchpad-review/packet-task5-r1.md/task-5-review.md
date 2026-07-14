### Task 5: Docs — codex-execution.md rewrite, README Codex section
- [ ] Done

**Files:**
- Modify: `skills/planning/codex-execution.md` (full rewrite)
- Modify: `README.md` (Codex install/usage section)

**Spec:** Runner, Halt, Retirements

**Interface:** codex-execution.md contract content — runner invocation line (`python3 <plugin-root>/scripts/forge-run.py <plan.md> --spec <spec.md>`); orchestrator role reduced to: invoke runner, relay escalation receipts verbatim, hold human gates, never absorb work inline; resume procedure (re-invoke with same `--run-dir` after human resolution: amend brief source, re-tier, bump one task to `max`, or defer); in-session subagents acceptable outside plan execution only. README: drop agent-copy install step and re-copy note; add runner invocation and `.forge/` gitignore note.

**Tests:** none (prose contracts; content checked at review).

**Acceptance:** `grep -c "codex exec" skills/planning/codex-execution.md` ≥ 1; `grep -c "nickname" skills/planning/codex-execution.md` = 0; `grep -c "codex/agents" README.md` = 0; `python3 -m pytest -q` passes.

**Tier:** standard

**Depends on:** Task 3.

````diff
diff --git a/README.md b/README.md
index c771ed5..c65549d 100644
--- a/README.md
+++ b/README.md
@@ -157,9 +157,28 @@ The `SessionStart` hook works on Codex without extra wiring — the shared
 `hooks/hooks.json` schema is compatible and Codex sets `CLAUDE_PLUGIN_ROOT`
 for plugin-hook compatibility.
 
+Plan execution runs through a deterministic runner instead of in-session
+subagent dispatch — one `codex exec` process per task, pinned model/effort
+per tier:
+
+```bash
+python3 "$CLAUDE_PLUGIN_ROOT/scripts/forge-run.py" <plan.md> --spec <spec.md>
+```
+
+See `skills/planning/codex-execution.md` for the invocation contract,
+halt/resume, and the orchestrator's reduced role. Receipts land in
+`.forge/runs/<timestamp>/`, uncommitted — the runner writes a self-ignoring
+`.forge/.gitignore` (`*`) on first run, so there's no target-repo setup.
+
 <details>
 <summary><strong>Known Codex caveats</strong></summary>
 
+These apply to ad-hoc in-session Codex subagents (exploration, one-off
+review) — the only place forge still spawns them. Plan execution goes
+through `forge-run.py`'s one-`codex exec`-process-per-task instead, which
+sidesteps both issues by construction (no parent-model inheritance, no
+completed-worker accumulation).
+
 - Subagent selection has known regressions (custom-agent selection broke in
   v0.137.0 and spawned agents silently inherited the parent model). If
   spawned agents run the wrong model, check acceptance-command output rather
@@ -168,8 +187,6 @@ for plugin-hook compatibility.
   keep counting against the thread limit
   ([openai/codex#19197](https://github.com/openai/codex/issues/19197),
   [openai/codex#22779](https://github.com/openai/codex/issues/22779)).
-  Sequential dispatch (`skills/planning/codex-execution.md`) keeps the pile
-  small; forge doesn't build cleanup machinery for a harness bug.
 
 </details>
 
diff --git a/skills/planning/codex-execution.md b/skills/planning/codex-execution.md
index 455953b..362cca4 100644
--- a/skills/planning/codex-execution.md
+++ b/skills/planning/codex-execution.md
@@ -1,15 +1,73 @@
 # Codex execution (no Workflow tool)
 
-Same plan, same tasks, same tiers — dispatched sequentially instead of pipelined, because Codex CLI has no Workflow tool to spawn/track parallel workers.
+Codex CLI has no Workflow tool to spawn/track parallel workers, so plan
+execution runs through `scripts/forge-run.py` — a deterministic runner that
+drives one fresh `codex exec` process per task instead of in-session
+subagent dispatch. The process boundary is what makes it deterministic: no
+parent-model inheritance, no child-thread quota accumulation.
 
-**Sequential dispatch only:** one worker at a time. Spawn a worker by naming the tier agent directly (e.g. "Have forge-standard implement task N"). `Depends on` order is enforced serially — never start task N+1 until task N's worker has reported back and review has passed. No pipelining, no worktree isolation.
+**Invocation:** after the execution approval gate, the orchestrator runs:
 
-**Briefs and review packets unchanged:** generate each worker's brief with `scripts/extract-brief.py`; route diffs through `scripts/review-packet.py`. Same mechanics as pipelined execution — only the dispatch loop is different. Both live in the plugin root's `scripts/` directory (see the location note in SKILL.md).
+```bash
+python3 "$CLAUDE_PLUGIN_ROOT/scripts/forge-run.py" <plan.md> --spec <spec.md>
+```
 
-**Orchestrator no-work rule (hard):** during dispatched execution the orchestrator never opens or edits implementation files — dispatch, read the one-paragraph report, run acceptance commands, update the ledger. Catching yourself about to edit a source file means you owed a dispatch instead. A worker that fails the 2-iteration rework cap escalates to the user with the outstanding findings; the orchestrator never absorbs the work inline.
+That single call is whole-plan scope. The runner owns the task loop
+(`Depends on` order, sequential, one worker at a time — no pipelining, no
+worktree isolation), brief generation, worker dispatch, acceptance-command
+execution, review dispatch, the rework cap, receipts, and plan-checkbox
+ledger annotations. It reuses `extract-brief.py` and `review-packet.py` for
+all plan/spec parsing — no duplicated heading grammar.
 
-**Dispatch ledger:** plan-file checkboxes double as the worker tracker. On dispatch, annotate the task line with the worker nickname (e.g. `dispatched: forge-standard-2`). On completion, annotate the review outcome. Agent-list rows resolve to plan lines via the tier-prefixed nicknames.
+**Orchestrator's role is reduced to four things:** invoke the runner, relay
+escalation receipts to the user verbatim, hold the human gates (execution
+approval before invoking, resolution decisions on halt), and never absorb
+work inline. If a `codex exec` call inside the runner fails or halts, the
+fix is a human decision and a re-invocation — not the orchestrator editing
+source files or reasoning through the fix itself.
 
-**No lifecycle machinery:** worker accumulation/quota bugs are harness-side (openai/codex #19197, #22779) — sequential dispatch minimizes accumulation by construction; nothing else is built to work around it.
+**Halt / escalation:** the runner halts mechanically — never a judgment
+call — at the rework cap (2 iterations: initial attempt + 1 rework), on an
+unparseable reviewer verdict, and on brief/review-packet generation errors
+(existing fail-loud contracts). On halt it writes a receipt with the
+outstanding findings, exits non-zero, and starts no further tasks. The
+orchestrator's only job at that point is relaying the receipt's contents to
+the user — not summarizing, not softening, not attempting the fix itself.
 
-**Review flow, proportional review, deferral rule, final review:** identical to the Execution section — trivial tasks skip subagent review, standard/complex tasks get the combined review, non-spec scope may be deferred with a DEFERRALS.md entry, and a final broad review runs once every task passes. All executed sequentially, same as everything else in this mode.
+**Resume:** re-invoke the same command with the same `--run-dir` after the
+human has resolved the halt. The runner skips every task whose latest
+receipt status is `passed` and resumes at the escalated task. Resolution
+before re-invoking is a human decision among:
+
+- amend the brief source (plan or spec) to correct what the reviewer flagged;
+- re-tier the task (trivial/standard/complex) if routing was wrong for the work;
+- bump the escalated task to `max` reasoning effort for one re-run — a
+  human-only escalation, never a default, and never `ultra` at any tier
+  (prohibited everywhere because it spawns subagents inside the worker,
+  breaking brief isolation);
+- defer the finding (`docs/forge/DEFERRALS.md`) if it's non-spec scope, then
+  resume.
+
+**Tier routing:** unchanged in substance from the pipelined path — trivial
+tasks skip reviewer dispatch (acceptance commands are the whole
+verification), standard and complex tasks get a reviewer dispatched via
+`codex exec` after acceptance passes. Model/effort per tier lives in exactly
+one table inside `forge-run.py` (`TIER_MAP`) — not duplicated here or in any
+per-tier config file.
+
+**Final review:** once every task passes, the runner dispatches one more
+`codex exec` call (sol/high) against the whole-plan diff and spec —
+integration issues a per-task review can't see. Findings there halt with
+`escalated-final-review` status; there's no rework loop at plan level, only
+a human gate.
+
+**Receipts:** ephemeral, `.forge/runs/<timestamp>/` (or an explicit
+`--run-dir`), one JSON receipt per task attempt plus a `run.json` summary.
+The runner self-manages `.forge/`'s gitignore on first write — no
+target-repo setup required. Plan-file checkboxes remain the durable,
+human-readable record (`— passed, N attempt(s)` / `— escalated: <one-liner>`).
+
+**In-session Codex subagents remain acceptable outside plan execution** —
+ad-hoc exploration, one-off review, anything that isn't dispatched by the
+runner. No forge machinery spawns them; the runner's `codex exec` calls are
+the only dispatch path a plan ever goes through.
````
