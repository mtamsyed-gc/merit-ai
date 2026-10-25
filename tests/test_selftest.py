"""The launcher chain runs end to end on synthetic data (P1 exit gate)."""
import subprocess
import sys

from helpers import ROOT, done, ok

r = subprocess.run([sys.executable, str(ROOT / "run.py"), "selftest", "--scale", "0.02"], capture_output=True,
                   text=True, cwd="/")
ok(r.returncode == 0, "run.py selftest exits 0 from any working directory")
ok("SELF-TEST PASSED" in r.stdout, "self-test reports PASSED")
ok((ROOT / "out" / "selftest_reports" / "G1_selftest.xlsx").exists(), "gate report written")
for name in ("00_Self_test.cmd", "01_Run_tests.cmd"):
    t = (ROOT / "launchers" / name).read_text(encoding="utf-8")
    ok("pushd \"%~dp0..\"" in t and "py " in t, f"{name} runs from its own folder with the py launcher")
    ok(".ps1" not in t, f"{name} uses no PowerShell script")
done("test_selftest")
