"""Tests for hooks/user-prompt-submit — the Codex UserPromptSubmit hook that
injects live run state. Runs the actual hook script as a subprocess with a temp
cwd holding a .forge/runs/ fixture; asserts the emitted additionalContext JSON.
"""
import json
import os
import pathlib
import subprocess
import sys
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "user-prompt-submit"


def _make_run(cwd, name, status, tasks, receipts=None, contract_error=None):
    rd = os.path.join(cwd, ".forge", "runs", name)
    os.makedirs(rd)
    data = {"plan": "/p", "spec": "/s", "status": status,
            "base_commit": "abc", "tasks": tasks}
    if contract_error is not None:
        data["contract_error"] = contract_error
    with open(os.path.join(rd, "run.json"), "w") as f:
        json.dump(data, f)
    for r in receipts or []:
        path = os.path.join(rd, "task-{}-attempt-{}.json".format(r["n"], r["a"]))
        with open(path, "w") as f:
            json.dump({"task_number": r["n"], "attempt": r["a"],
                       "status": r["status"],
                       "outstanding_findings": r.get("findings", [])}, f)
    return rd


def _summary(n, status, attempts=1):
    return {"number": n, "title": "T{}".format(n), "tier": "standard",
            "status": status, "attempts": attempts, "commit": None}


def _age(path, hours):
    old = time.time() - hours * 3600
    for root, _, files in os.walk(path):
        for name in files:
            os.utime(os.path.join(root, name), (old, old))


def _run_hook(cwd, hook_input=None):
    # Default input carries a Codex-style turn_id (no Claude transcript_path), so
    # the harness gate treats it as a Codex session and the hook fires.
    payload = {"cwd": cwd, "prompt": "hi", "turn_id": "t1"}
    if hook_input is not None:
        payload = hook_input
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=cwd, input=json.dumps(payload),
        capture_output=True, text=True,
    )


class PromptHookTests(unittest.TestCase):
    def test_silent_without_forge_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            r = _run_hook(d)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "")

    def test_silent_when_only_run_is_stale_terminal(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rd = _make_run(d, "20260101T000000", "passed", [_summary(1, "passed")])
            _age(rd, 13)
            r = _run_hook(d)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "")

    def test_live_run_emits_valid_json_within_line_cap(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _make_run(d, "20260101T000000", "running",
                      [_summary(n, "passed") for n in range(1, 4)])
            r = _run_hook(d)
            self.assertEqual(r.returncode, 0)
            payload = json.loads(r.stdout)
            block = payload["hookSpecificOutput"]["additionalContext"]
            self.assertEqual(payload["hookSpecificOutput"]["hookEventName"],
                             "UserPromptSubmit")
            self.assertLessEqual(len(block.splitlines()), 6)

    def test_completed_recent_run_emits_block(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _make_run(d, "20260101T000000", "passed", [_summary(1, "passed")])
            r = _run_hook(d)
            self.assertTrue(r.stdout.strip())
            json.loads(r.stdout)

    def test_halted_run_block_includes_reason(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _make_run(d, "20260101T000000", "escalated",
                      [_summary(1, "passed"), _summary(2, "escalated")],
                      receipts=[{"n": 2, "a": 2, "status": "escalated",
                                 "findings": ["boom"]}])
            r = _run_hook(d)
            block = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("task 2", block.lower())

    def test_latest_run_chosen_when_multiple(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _make_run(d, "20260101T000000", "passed", [_summary(1, "passed")])
            _make_run(d, "20260201T000000", "running", [_summary(1, "passed")])
            r = _run_hook(d)
            block = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("RUNNING", block)

    def test_silent_under_claude_input(self):
        # Claude's UserPromptSubmit input carries transcript_path (and no Codex
        # turn_id) -> the harness gate suppresses; session awareness is Codex-only.
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _make_run(d, "20260101T000000", "running", [_summary(1, "passed")])
            r = _run_hook(d, hook_input={"cwd": d, "prompt": "hi",
                                         "transcript_path": "/tmp/t.jsonl"})
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "")

    def test_fires_under_codex_input(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _make_run(d, "20260101T000000", "running", [_summary(1, "passed")])
            r = _run_hook(d, hook_input={"cwd": d, "prompt": "hi", "turn_id": "t1"})
            self.assertTrue(r.stdout.strip())
            json.loads(r.stdout)

    def test_ambiguous_input_fires(self):
        # Neither transcript_path nor turn_id -> err toward firing (degrades to
        # option 1: fires in both, silent when no run).
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _make_run(d, "20260101T000000", "running", [_summary(1, "passed")])
            r = _run_hook(d, hook_input={"cwd": d, "prompt": "hi"})
            self.assertTrue(r.stdout.strip())

    def test_malformed_run_json_is_silent_exit_0(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rd = os.path.join(d, ".forge", "runs", "20260101T000000")
            os.makedirs(rd)
            with open(os.path.join(rd, "run.json"), "w") as f:
                f.write("{not valid json")
            r = _run_hook(d)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
