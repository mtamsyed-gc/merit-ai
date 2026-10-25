"""Merit AI command line. Launchers in launchers/ call this as `py run.py <command>`.

Commands
  selftest [--scale S]            control files, contract pin, synthetic pack, G1 checks built so far, gate report
  synth --out DIR [--scale S] [--seed N] [--stamp-contract]
                                  write a synthetic pool pack (fictitious cedants as Merit run folders)
  contract RUN_DIR                schema check of one Merit run folder against the pinned contract
  gate G1 RUN_DIR [--out DIR] [--subject NAME] [--signoffs FILE]
                                  run a gate on one folder and write its report
  signoff CHECK SUBJECT FINGERPRINT SIGNER ROLE REASON --signoffs FILE
                                  record a sign-off for one Flag finding (fingerprint from the gate report)
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_missing = []
for _m in ("duckdb", "pyarrow", "pandas", "numpy", "openpyxl", "xlsxwriter", "scipy", "statsmodels"):
    try:
        __import__(_m)
    except ImportError:
        _missing.append(_m)
if _missing:
    print(f"Python {sys.version.split()[0]} at {sys.executable} is missing: {', '.join(_missing)}.")
    print("Install once in a normal PowerShell window:  py -m pip install --user -r requirements.txt")
    sys.exit(5)

from meritai import VERSION, contract, control, gates, synth  # noqa: E402

OUT = HERE / "out"


def say(msg=""):
    print(msg, flush=True)


def cmd_selftest(a):
    say(f"Merit AI {VERSION} self-test (Python {sys.version.split()[0]})")
    say("1/5 Control files ...")
    errs = control.validate()
    if errs:
        for e in errs:
            say(f"   STOP {e}")
        return 2
    say(f"    OK: {len(control.checks())} gate checks registered, {len(gates.built())} built "
        f"({', '.join(gates.built())})")
    say("2/5 Pinned Merit contract ...")
    pin, _ = contract.load_pin()
    say(f"    OK: contract {pin['version']} (hash verified)")
    say("3/5 Synthetic pool pack ...")
    pack = OUT / "selftest_pack"
    if pack.exists():
        shutil.rmtree(pack)
    truth = synth.generate(pack, scale=a.scale, progress=lambda m: say("   " + m), overwrite=True)
    say(f"    OK: {len(truth['cedants'])} fictitious cedants in {pack}")
    say("4/5 Gate G1 on each cedant's Merit run (checks built so far) ...")
    runs = []
    for code in sorted(truth["cedants"]):
        r = gates.run_gate("G1", {"run_dir": pack / code / "04_Outputs"}, code, allow_incomplete=True)
        runs.append(r)
        say(f"    {code}: {r.outcome}  " + ", ".join(f"{x.check_id} {x.status}" for x in r.results
                                                  if x.status != "NOT_BUILT"))
    say("5/5 Gate report ...")
    xl, md = gates.write_report(runs, OUT / "selftest_reports", "G1_selftest")
    say(f"    {xl}")
    bad = [r for r in runs if r.outcome == "STOP"]
    if bad:
        say(f"SELF-TEST FAILED: {len(bad)} cedant(s) stopped at G1")
        return 1
    say("SELF-TEST PASSED")
    return 0


def cmd_synth(a):
    t = synth.generate(Path(a.out), seed=a.seed, scale=a.scale, stamp_contract=a.stamp_contract,
                       overwrite=a.overwrite)
    say(f"{len(t['cedants'])} cedants written to {a.out}")
    return 0


def cmd_contract(a):
    issues = contract.check_schema(a.run_dir)
    for i in issues:
        say(f"{i['kind']:15s} {i['table']} {i['column']} {i['count']} {i['example']}")
    hard = [i for i in issues if i["kind"] != "extra_column"]
    say("OK" if not hard else f"{len(hard)} problem(s)")
    return 1 if hard else 0


def cmd_gate(a):
    subject = a.subject or Path(a.run_dir).resolve().parent.name
    so = gates.load_signoffs(a.signoffs)
    r = gates.run_gate(a.gate, {"run_dir": Path(a.run_dir)}, subject, signoffs=so, allow_incomplete=a.allow_incomplete)
    xl, md = gates.write_report([r], Path(a.out), f"{a.gate}_{subject}")
    for x in r.results:
        say(f"  {x.check_id:6s} {x.status:10s} {x.message}")
    say(f"{a.gate} {subject}: {r.outcome}   report: {xl}")
    return {"PASS": 0, "FLAG": 3, "INCOMPLETE": 4, "STOP": 1}[r.outcome.split(" ")[0]]


def cmd_signoff(a):
    gates.add_signoff(a.signoffs, a.check, a.subject, a.fingerprint, a.signer, a.role, a.reason)
    say(f"signed {a.check} for {a.subject} by {a.signer}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="run.py", description="Merit AI")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selftest")
    s.add_argument("--scale", type=float, default=0.05)
    s = sub.add_parser("synth")
    s.add_argument("--out", required=True)
    s.add_argument("--scale", type=float, default=0.1)
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--no-stamp", dest="stamp_contract", action="store_false",
                   help="write manifests without contract_version, as Merit before v7.3.2")
    s.add_argument("--overwrite", action="store_true", help="replace a non-empty output folder")
    s = sub.add_parser("contract")
    s.add_argument("run_dir")
    s = sub.add_parser("gate")
    s.add_argument("gate", choices=sorted(control.load("gates")["gates"]))
    s.add_argument("run_dir")
    s.add_argument("--out", default=str(OUT / "reports"))
    s.add_argument("--subject")
    s.add_argument("--signoffs")
    s.add_argument("--allow-incomplete", action="store_true")
    s = sub.add_parser("signoff")
    for x in ("check", "subject", "fingerprint", "signer", "role", "reason"):
        s.add_argument(x)
    s.add_argument("--signoffs", required=True)
    a = p.parse_args(argv)
    return {"selftest": cmd_selftest, "synth": cmd_synth, "contract": cmd_contract, "gate": cmd_gate,
            "signoff": cmd_signoff}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
