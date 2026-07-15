"""Suite-wide test setup.

Disable the runner's default macOS `osascript` notification modal for the whole
test run. Many tests execute real plans to completion (or escalation) via a
subprocess without `--notify`, and the darwin default would otherwise pop a real
desktop alert per run. Set at import so it is present before any test builds a
subprocess env via `os.environ.copy()`, propagating into every child. Tests that
pass an explicit `--notify CMD` are unaffected (that path is never gated); the
one unit test asserting the osascript default clears this var locally.
"""
import os

os.environ.setdefault("FORGE_NOTIFY_DISABLE", "1")
