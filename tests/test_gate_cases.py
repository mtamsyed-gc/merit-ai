"""Fail-on-purpose cases: every BUILT gate check has planted failures it must catch and clean cases it must pass.
The registry test at the end fails if a built check has no cases here (CLAUDE.md rule).
"""
import hashlib
import hmac

import pandas as pd
from helpers import copy_run, done, ok, pack

from meritai import gates

EID = "784-1990-1234567-1"


def _csv(run, table):
    return run / "csv" / f"{table}.csv"


def _set(run, table, col, row, value):
    p = _csv(run, table)
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    df.loc[row, col] = value
    df.to_csv(p, index=False)


def _drop(run, table, col):
    p = _csv(run, table)
    pd.read_csv(p, dtype=str, keep_default_na=False).drop(columns=[col]).to_csv(p, index=False)


def _add_col(run, table, name, value):
    p = _csv(run, table)
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    df[name] = value
    df.to_csv(p, index=False)


def _stamp(run, file, version):
    p = run / "csv" / file
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    pd.concat([df, pd.DataFrame([{"Key": "contract_version", "Value": version}])]).to_csv(p, index=False)


def _ragged(run, table, extra):
    with open(_csv(run, table), "a", encoding="utf-8") as f:
        f.write(extra + "\n")


def _hash_keys(run):
    for t in ("dim_life", "fact_claims"):
        p = _csv(run, t)
        df = pd.read_csv(p, dtype=str, keep_default_na=False)
        for c in ("MemKey", "PolKey", "LifeKey", "ClaimantKey"):
            if c in df:
                df[c] = [hmac.new(b"synthetic-secret", v.encode(), hashlib.sha256).hexdigest() for v in df[c]]
        df.to_csv(p, index=False)


def _parquet_eid(run):
    p = _csv(run, "cf_selected")
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    df.loc[0, "Source"] = EID
    (run / "parquet").mkdir(exist_ok=True)
    df.to_parquet(run / "parquet" / "cf_selected.parquet", index=False)


def run_check(cid, run, **ctx):
    gates.built()
    return gates.REGISTRY[cid]({"run_dir": run, **ctx})


d, _ = pack()

CASES = {
    "G1.1": [
        ("clean, unstamped -> FLAG (interim rule)", lambda r: None, "FLAG"),
        ("stamped with the pinned version -> PASS", lambda r: _stamp(r, "run_manifest_premium.csv", "IP4-8"), "PASS"),
        ("stamped with another version -> STOP", lambda r: _stamp(r, "run_manifest_premium.csv", "IP4-7"), "STOP"),
        ("conflicting stamps across manifests -> STOP",
         lambda r: (_stamp(r, "run_manifest_premium.csv", "IP4-8"), _stamp(r, "run_manifest_claims.csv", "IP4-7")),
         "STOP"),
        ("column missing -> STOP", lambda r: _drop(r, "fact_claims", "PayerShare"), "STOP"),
        ("date not yyyy-mm-dd -> STOP", lambda r: _set(r, "fact_member_month", "MonthStart", 0, "2026-7-1"), "STOP"),
        ("date with a time -> STOP", lambda r: _set(r, "dim_life", "CovStart", 0, "2026-07-01 13:45:00"), "STOP"),
        ("decimal in an integer column -> STOP", lambda r: _set(r, "dim_life", "UWY", 1, "2025.5"), "STOP"),
        ("hex in an integer column -> STOP", lambda r: _set(r, "dim_life", "CovDays", 1, "0x7E9"), "STOP"),
        ("infinite double -> STOP", lambda r: _set(r, "fact_claims", "PayerShare", 0, "inf"), "STOP"),
        ("table missing -> STOP", lambda r: _csv(r, "cf_selected").unlink(), "STOP"),
        ("manifest missing -> STOP", lambda r: [p.unlink() for p in (r / "csv").glob("run_manifest*.csv")], "STOP"),
        ("exceptions file lacks a contract column -> STOP", lambda r: _drop(r, "exceptions", "Message"), "STOP"),
        ("ragged row -> STOP", lambda r: _ragged(r, "fact_member_month", f"1,2,3,{EID}"), "STOP"),
        ("empty file -> STOP", lambda r: _csv(r, "ultimates").write_text("", encoding="utf-8"), "STOP"),
        ("header-only table reads (no rows) -> FLAG", lambda r: _csv(r, "ultimates").write_text(
            _csv(r, "ultimates").read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8"), "FLAG"),
    ],
    "G1.4": [
        ("clean -> PASS", lambda r: None, "PASS"),
        ("keys replaced by keyed hashes -> PASS (no false positive on hex tokens)", _hash_keys, "PASS"),
        ("long decimals and codes are not identifiers -> PASS",
         lambda r: (_set(r, "dim_life", "Contract Name", 3, "13.068493151"),
                    _set(r, "dim_life", "Plan / Category", 4, "0.7841990123456712"),
                    _set(r, "fact_claims", "ICD Code", 0, "S72.001A")), "PASS"),
        ("Emirates ID in a text column -> STOP", lambda r: _set(r, "dim_life", "Contract Name", 3, EID), "STOP"),
        ("Emirates ID without dashes -> STOP", lambda r: _set(r, "fact_claims", "ICD Description", 1, "784199012345671"),
         "STOP"),
        ("Emirates ID after a label -> STOP", lambda r: _set(r, "dim_life", "Plan / Category", 2, f"EID No.{EID}"),
         "STOP"),
        ("Emirates ID in a numeric column -> STOP", lambda r: _set(r, "fact_claims", "SrcOrder", 0, "784199012345671"),
         "STOP"),
        ("Emirates ID as a column header -> STOP", lambda r: _add_col(r, "dim_life", EID, ""), "STOP"),
        ("e-mail address -> STOP", lambda r: _set(r, "dim_life", "Distribution", 5, "someone@example.com"), "STOP"),
        ("UAE mobile, spaced -> STOP", lambda r: _set(r, "fact_claims", "Provider Name", 2, "050 123 4567"), "STOP"),
        ("UAE mobile after 'Tel.' -> STOP", lambda r: _set(r, "fact_claims", "Provider Name", 2, "Tel.0501234567"),
         "STOP"),
        ("UAE mobile, 971 without + -> STOP", lambda r: _set(r, "fact_claims", "Provider Name", 2, "971501234567"),
         "STOP"),
        ("UAE mobile, +971 (0) form -> STOP", lambda r: _set(r, "dim_life", "Contract Name", 1, "+971 (0)50 123 4567"),
         "STOP"),
        ("identifier in an exceptions message -> STOP",
         lambda r: _set(r, "exceptions", "Message", 0, "member +971501234567 not found"), "STOP"),
        ("identifier in a recon value -> STOP", lambda r: _set(r, "recon_premium", "Value", 0, "784199012345671"), "STOP"),
        ("identifier in an extra recon column -> STOP", lambda r: _add_col(r, "recon_claims", "note", "050 123 4567"),
         "STOP"),
        ("identifier in a manifest value -> STOP",
         lambda r: _set(r, "run_manifest_premium", "Value", 0, "contact 0501234567"), "STOP"),
        ("identifier in a parquet table -> STOP", _parquet_eid, "STOP"),
        ("unreadable table -> STOP", lambda r: _ragged(r, "exceptions", f"a,b,c,d,e,f,g,{EID}"), "STOP"),
    ],
}

LEAKS = (EID, "784199012345671", "@example", "0501234567", "050 123 4567", "784-1990")
for cid, cases in CASES.items():
    for label, mutate, expect in cases:
        run = copy_run(d)
        mutate(run)
        res = run_check(cid, run)
        ok(res.status == expect, f"{cid}: {label} (got {res.status}: {res.message[:70]})")
        blob = res.message + " " + " ".join(str(x) for x in res.details)
        ok(not any(s in blob for s in LEAKS), f"{cid}: {label}: no value or unknown header echoed")
        g = gates.run_gate("G1", {"run_dir": run}, "X", allow_incomplete=True)
        xl, md = gates.write_report([g], run.parent / "rep", "r")
        ok(not any(s in md.read_text(encoding="utf-8") for s in LEAKS), f"{cid}: {label}: report free of values")

run = copy_run(d)
res = run_check("G1.4", run, allowed_columns={"dim_life": ["LifeID"]})
ok(res.status == "STOP" and "outside the allowed list" in res.message, "G1.4: column outside the allow-list -> STOP")

built = set(gates.built())
ok(built == set(CASES), f"every built check has fail-on-purpose cases (built: {sorted(built)})")
done("test_gate_cases")
