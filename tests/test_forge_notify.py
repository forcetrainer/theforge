"""Tests for forge-run.py --notify: fire_notify plumbing and the three terminal
call sites (escalation, contract error, completion).

Unit tests monkeypatch subprocess.Popen so no real notifier (and no real
osascript alert) ever fires. Integration tests run the CLI with a fake notifier
script that records the event + summary it received.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from _forge_support import (
    MINIMAL_SPEC,
    PLAN_ACC_FAIL,
    PLAN_PASS,
    SCRIPT_PATH,
    forge_run,
    write_fake_codex,
)

NOTIFIER_SRC = """#!/usr/bin/env python3
import sys
with open(sys.argv[1], "a") as f:
    f.write("\\t".join(sys.argv[2:]) + "\\n")
"""


def _write_notifier(dirpath):
    path = os.path.join(dirpath, "notifier.py")
    with open(path, "w") as f:
        f.write(NOTIFIER_SRC)
    return path


def _wait_for(path, timeout=5.0):
    """Poll for a fire-and-forget notifier's log line (Popen does not wait)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path) as f:
                return f.read()
        time.sleep(0.02)
    return ""


class FireNotifyUnitTests(unittest.TestCase):
    def test_cmd_receives_event_and_summary_as_trailing_argv(self):
        calls = []
        with mock.patch.object(forge_run.subprocess, "Popen",
                               side_effect=lambda argv, **k: calls.append(argv)):
            forge_run.fire_notify("escalated", "task 2 escalated", cmd="python3 n.py log")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-2:], ["escalated", "task 2 escalated"])

    def test_default_on_darwin_uses_osascript(self):
        calls = []
        with mock.patch.dict(os.environ, {"FORGE_NOTIFY_DISABLE": ""}), \
             mock.patch.object(forge_run.sys, "platform", "darwin"), \
             mock.patch.object(forge_run.subprocess, "Popen",
                               side_effect=lambda argv, **k: calls.append(argv)):
            forge_run.fire_notify("completed", "3 tasks passed", cmd=None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "osascript")
        self.assertIn("3 tasks passed", " ".join(calls[0]))

    def test_default_off_darwin_writes_stderr_and_fires_nothing(self):
        calls = []
        err = mock.MagicMock()
        with mock.patch.dict(os.environ, {"FORGE_NOTIFY_DISABLE": ""}), \
             mock.patch.object(forge_run.sys, "platform", "linux"), \
             mock.patch.object(forge_run.sys, "stderr", err), \
             mock.patch.object(forge_run.subprocess, "Popen",
                               side_effect=lambda argv, **k: calls.append(argv)):
            forge_run.fire_notify("completed", "3 tasks passed", cmd=None)
        self.assertEqual(calls, [])
        self.assertTrue(err.write.called)

    def test_broken_cmd_never_raises(self):
        with mock.patch.object(forge_run.subprocess, "Popen",
                               side_effect=OSError("boom")):
            # must not propagate
            forge_run.fire_notify("completed", "done", cmd="python3 n.py log")


class NotifyCallSiteTests(unittest.TestCase):
    def _run(self, cwd, plan_text, notify_cmd=None, extra=None):
        plan_path = os.path.join(cwd, "plan.md")
        spec_path = os.path.join(cwd, "spec.md")
        with open(plan_path, "w") as f:
            f.write(plan_text)
        with open(spec_path, "w") as f:
            f.write(MINIMAL_SPEC)
        argv = [sys.executable, str(SCRIPT_PATH), plan_path, "--spec", spec_path,
                "--run-dir", os.path.join(cwd, "run"),
                "--codex-bin", write_fake_codex(cwd)]
        if notify_cmd is not None:
            argv += ["--notify", notify_cmd]
        argv += extra or []
        env = os.environ.copy()
        env["FORGE_FAKE_LOG"] = os.path.join(cwd, "codex.log")
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=env)

    def test_completed_fires_completed_event(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "notify.log")
            cmd = "{} {} {}".format(sys.executable, _write_notifier(d), log)
            r = self._run(d, PLAN_PASS, notify_cmd=cmd)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("completed", _wait_for(log))

    def test_escalation_fires_escalated_event(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "notify.log")
            cmd = "{} {} {}".format(sys.executable, _write_notifier(d), log)
            r = self._run(d, PLAN_ACC_FAIL, notify_cmd=cmd)
            self.assertEqual(r.returncode, 2)
            self.assertIn("escalated", _wait_for(log))

    def test_contract_error_fires_contract_error_event(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "notify.log")
            cmd = "{} {} {}".format(sys.executable, _write_notifier(d), log)
            r = self._run(d, PLAN_PASS, notify_cmd=cmd, extra=["--effort", "99=high"])
            self.assertEqual(r.returncode, 1)
            self.assertIn("contract-error", _wait_for(log))

    def test_broken_notifier_does_not_change_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(d, PLAN_PASS, notify_cmd="/nonexistent/notifier-xyz")
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
