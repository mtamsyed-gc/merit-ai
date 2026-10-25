"""Run every tests/test_*.py as its own process. Exit 0 only if all pass.

  py tests/run_all.py            all suites
  py tests/run_all.py synth      suites whose name contains 'synth'
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else ""
    suites = sorted(p for p in HERE.glob("test_*.py") if pat in p.stem)
    failed = []
    t0 = time.time()
    for s in suites:
        t = time.time()
        r = subprocess.run([sys.executable, str(s)], capture_output=True, text=True)
        status = "PASS" if r.returncode == 0 else "FAIL"
        print(f"{status}  {s.stem:28s} {time.time() - t:6.1f} s")
        if r.returncode != 0:
            failed.append(s.stem)
            print(r.stdout[-4000:])
            print(r.stderr[-4000:])
    print(f"\n{len(suites) - len(failed)}/{len(suites)} suites passed in {time.time() - t0:.0f} s")
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
