"""Control files: valid, complete, consistent with SPEC.md and the owner's decisions."""
import re

from helpers import ROOT, done, ok

from meritai import control

ok(control.validate() == [], "control files validate")
checks = control.checks()
ok(len(checks) == 48, "48 gate checks registered (SPEC gate register)")
per_gate = {}
for c in checks.values():
    per_gate[c["gate"]] = per_gate.get(c["gate"], 0) + 1
ok(per_gate == {"G1": 8, "G2": 7, "G3": 7, "G4": 6, "G5": 7, "G6": 8, "G7": 5}, "checks per gate as in SPEC")

spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")
spec_ids = set(re.findall(r"^\|\s*(G\d\.\d)\s*\|", spec, flags=re.M))
ok(spec_ids == set(checks), f"registry ids equal the check ids in SPEC.md gate tables ({len(spec_ids)})")
for cid, c in checks.items():
    row = re.search(rf"^\|\s*{re.escape(cid)}\s*\|(.*)$", spec, flags=re.M).group(1)
    last = row.strip().rstrip("|").split("|")[-1].strip()
    lvl = c["on_fail"]
    expect = {"Stop": "Stop", "Flag": "Flag", "Info": "Info", "Auto": ("roll-up", "labelled", "Auto")}[lvl]
    hit = any(e.lower() in last.lower() for e in (expect if isinstance(expect, tuple) else (expect,)))
    ok(hit, f"{cid} on_fail {lvl} matches SPEC action '{last[:40]}'")

phases = set(re.findall(r"\*\*(P[1-7]) ", spec))
ok(phases == {f"P{i}" for i in range(1, 8)}, "SPEC.md carries the seven phases in text")
ok({c["phase"] for c in checks.values()} <= phases, "every check's build phase is a SPEC phase")

net = control.load("crosswalk")["network"]
ok(sorted(net["by_tpa"]) == ["AAFIYA", "E-CARE", "MEDNET", "NAS", "NEXTCARE"], "tier map covers the five TPAs (D-1)")
spot = [("MEDNET", "Silk Road", "VN"), ("NEXTCARE", "GN+", "CN"), ("E-CARE", "Classic", "RN2"),
        ("AAFIYA", "Diamond", "GN"), ("NAS", "SRN", "RN2"), ("NAS", "WN", "RN3"),
        ("NEXTCARE", "RN3 (OP clinics only)", "VN"), ("MEDNET", "Silver Classic", "GN_XM"),
        ("AAFIYA", "APN (Enhanced EBP)", "VN"), ("NAS", "unknown network", "Unmapped")]
for tpa, raw, tier in spot:
    ok(control.network_tier(tpa, raw) == tier, f"{tpa} {raw} -> {tier}")
ok(net["rollup"] == {"CN": "Top", "GN": "Top", "GN_XM": "Top", "RN": "Mid", "RN2": "Mid", "RN3": "Basic",
                     "VN": "Basic"}, "roll-up Top / Mid / Basic as accepted")
ok(net["pooled_as"] == {"GN_XM": "GN"}, "GN excl. Mediclinic pooled as GN with its own label")

d = control.load("disclosure")["classes"]
ok(d["loss_cost"] == {"min_cedants": 3, "max_single_share": 0.5, "min_life_years": 500}, "D-4 loss-cost class")
ok(d["pricing"] == {"min_cedants": 5, "max_single_share": 0.25, "min_life_years": 1000}, "D-4 pricing class")
th = control.load("thresholds")
ok(th["checks"]["G1.3"]["full_min"] == 0.95 and th["checks"]["G1.3"]["restricted_min"] == 0.85, "D-2 bands 95 / 85")
ok(th["credibility"]["p"] == 0.90 and th["credibility"]["k"] == 0.10 and th["credibility"]["cv_basis"] == "capped",
   "D-3 credibility 90% / 10%, capped CV")
ok(th["credibility"]["badges"] == {"high_min": 0.7, "medium_min": 0.3}, "D-3 badges 0.7 / 0.3")
ok(th["model_minimums"]["M2"]["cedants"] == 5, "D-3 M2 needs 5 cedants")
ok(th["large_claim"]["provisional_threshold_aed"] == 500000, "D-7 provisional threshold AED 500k")
ok(th["cadence"]["recalibration_finish_by_month"] == 4, "D-10 recalibration finished by April")
ok(th["trend"]["mode"] == "benchmark_only" and th["trend"]["pricing_default_pa"] == 0.10, "D-5 trend benchmark only")
done("test_control")
