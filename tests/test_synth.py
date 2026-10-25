"""Synthetic pool generator: deterministic, conserving, and drawn from the planted model.

The planted-model tests are independent of the generator's own bookkeeping: expected claim counts and severities
are rebuilt here from plant.json and the OUTPUT tables only (member-months, dim_life, fact_claims), through the
crosswalk, then compared with the claims actually written.
"""
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from helpers import done, ok, pack, tmpdir

from meritai import control, synth

P = synth.load_plant()

# ---------------------------------------------------------------- determinism and pack hygiene
a, b, c = (tmpdir('t_') for _ in range(3))
ta = synth.generate(a, scale=0.02, progress=lambda m: None)
tb = synth.generate(b, scale=0.02, progress=lambda m: None)
tc = synth.generate(c, seed=7, scale=0.02, progress=lambda m: None)
ok(ta["files"] == tb["files"], "same seed: byte-identical files")
ok((a / "truth.json").read_bytes() == (b / "truth.json").read_bytes(), "same seed: identical truth.json")
ok(ta["files"] != tc["files"], "different seed: different files")
try:
    synth.generate(a, scale=0.02, progress=lambda m: None)
    ok(False, "refuses to write into a non-empty folder")
except FileExistsError:
    ok(True, "refuses to write into a non-empty folder")
(a / "C99").mkdir()
synth.generate(a, scale=0.02, progress=lambda m: None, overwrite=True)
ok(not (a / "C99").exists(), "overwrite clears stale cedant folders")

# ---------------------------------------------------------------- conservation
d, truth = pack(scale=0.25)
ok(set(truth["cedants"]) == {x["code"] for x in P["cedants"]}, "every planted cedant written")
for code, t in sorted(truth["cedants"].items()):
    run = d / code / "04_Outputs" / "csv"
    n_fc = len(pd.read_csv(run / "fact_claims.csv", usecols=["ClaimKey"]))
    ok(t["lines_drawn"] == t["lines_reported"] + t["lines_unreported"], f"{code} drawn = reported + unreported")
    ok(t["lines_reported"] == t["lines_matched"] + t["lines_unmatched"], f"{code} reported = matched + unmatched")
    ok(n_fc == t["lines_matched"], f"{code} fact_claims rows = matched lines")
    rc = pd.read_csv(run / "recon_claims.csv")
    ok(int(rc["unmatched_lines"].sum()) == t["lines_unmatched"], f"{code} recon unmatched = truth")
    rp = pd.read_csv(run / "recon_premium.csv")
    ok(rp[rp.Measure.str.startswith("FanDiff")]["Value"].abs().max() < 0.01, f"{code} member-month fan ties")

# ---------------------------------------------------------------- independent expected counts
cw = control.load("crosswalk")
reg_map = cw["regulator"]["from_region_group"]
season = np.array(P["seasonality"]) / np.mean(P["seasonality"])
fr, sr, tr = P["freq_rel"], P["sev_rel"], P["trend"]
base = pd.Timestamp(P["dates"]["trend_base_date"])
xm = pd.Timestamp(P["dates"]["claims_extract_date"])
xi = xm.year * 12 + xm.month - 1
GROUPS = {"OPall": ["OP", "Pharmacy"], "IP": ["IP"], "Maternity": ["Maternity"], "Dental": ["Dental"],
          "Optical": ["Optical"]}


def group_of(fc):
    g = pd.Series("OPall", index=fc.index)
    g[fc["FOB"] == "In-Patient"] = "IP"
    g[fc["FOB"] == "Maternity"] = "Maternity"
    g[fc["FOB"] == "Dental"] = "Dental"
    g[fc["FOB"] == "Optical"] = "Optical"
    return g


exp_rows, obs_rows, sev_rows = [], [], []
for cp in P["cedants"]:
    code = cp["code"]
    run = d / code / "04_Outputs" / "csv"
    dim = pd.read_csv(run / "dim_life.csv", usecols=["LifeID", "TPA", "Network", "Region Group", "AgeBand", "Gender",
                                                      "Gender Group", "PolicyTypeUsed", "UWY", "Master Contract ID"])
    dim["polfx"] = dim["Master Contract ID"].map(truth["cedants"][code]["policyholder_effects"]["by_master_contract"])
    dim["tier"] = [control.network_tier(t, n) for t, n in zip(dim["TPA"], dim["Network"])]
    dim["reg"] = dim["Region Group"].map(reg_map)
    fmm = pd.read_csv(run / "fact_member_month.csv", usecols=["LifeID", "MonthStart", "EarnedLY_Gross"])
    m = fmm.merge(dim, on="LifeID", how="left", validate="many_to_one")
    ms = pd.to_datetime(m["MonthStart"])
    t = ((ms + pd.Timedelta(days=14)) - base).dt.days / 365.25
    mi = ms.dt.year * 12 + ms.dt.month - 1
    seas = season[(ms.dt.month - 1).values]
    common = (m["tier"].map(fr["tier"]) * m["reg"].map(fr["regulator"]) * m["PolicyTypeUsed"].map(fr["policy_type"])
              * truth["cedants"][code]["cedant_effect"] * m["polfx"] * m["EarnedLY_Gross"] * (1 + tr["freq_pa"]) ** t * seas)
    agegen = m["AgeBand"].map(fr["age_band"]) * m["Gender"].map(fr["gender"])
    pmf = {k: np.array(v) for k, v in P["reporting"]["report_lag_pmf"].items()}
    lag = (xi - mi).clip(0, 12).astype(int)
    rep = np.array([np.cumsum(pmf[tp])[min(lg, len(pmf[tp]) - 1)] for tp, lg in zip(m["TPA"], lag)])
    keep = rep * cp["match_rate"]
    lam = {}
    lam["OPall"] = (P["benefits"]["OP"]["freq"] + P["benefits"]["Pharmacy"]["freq"]) * common * agegen
    lam["IP"] = P["benefits"]["IP"]["freq"] * common * agegen + P["large_loss"]["rate_per_1000_ly"] / 1000 * m["EarnedLY_Gross"]
    lam["Maternity"] = P["benefits"]["Maternity"]["freq"] * common * (m["Gender Group"] == "Maternity Eligible Female")
    lam["Dental"] = P["benefits"]["Dental"]["freq"] * common * agegen
    lam["Optical"] = P["benefits"]["Optical"]["freq"] * common * agegen
    for g, v in lam.items():
        exp_rows.append(pd.DataFrame({"group": g, "tier": m["tier"], "reg": m["reg"], "age": m["AgeBand"],
                                      "year": ms.dt.year, "e": v * keep}))
    fc = pd.read_csv(run / "fact_claims.csv", usecols=["LifeID", "FOB", "Provider Type", "IncurredMonth", "PayerShare"])
    fc = fc.merge(dim[["LifeID", "tier", "reg", "AgeBand"]], on="LifeID", how="left", validate="many_to_one")
    fc["group"] = group_of(fc)
    im = pd.to_datetime(fc["IncurredMonth"])
    obs_rows.append(pd.DataFrame({"group": fc["group"], "tier": fc["tier"], "reg": fc["reg"], "age": fc["AgeBand"],
                                  "year": im.dt.year}))
    op = fc[(fc["group"] == "OPall") & (fc["Provider Type"] != "Pharmacy")]
    oim = pd.to_datetime(op["IncurredMonth"])
    ot = ((oim + pd.Timedelta(days=14)) - base).dt.days / 365.25
    sev_rows.append(pd.DataFrame({"tier": op["tier"], "year": oim.dt.year, "x": op["PayerShare"],
                                  "mu": P["benefits"]["OP"]["sev_mean"] * op["tier"].map(sr["tier"])
                                  * op["reg"].map(sr["regulator"]) * (1 + tr["sev_pa"]) ** ot}))
E = pd.concat(exp_rows)
O = pd.concat(obs_rows)
worst = (0.0, "")
cells = 0
for fac in ("tier", "reg", "age", "year"):
    e = E.groupby(["group", fac])["e"].sum()
    o = O.groupby(["group", fac]).size().reindex(e.index, fill_value=0)
    for k in e.index:
        if e[k] < 50:
            continue
        cells += 1
        tol = 4 / math.sqrt(e[k]) + 0.005         # Poisson noise only: planted effects are applied exactly
        dev = abs(o[k] / e[k] - 1)
        if dev / tol > worst[0]:
            worst = (dev / tol, f"{k} A/E {o[k] / e[k]:.3f}")
ok(cells > 40 and worst[0] < 1, f"claim counts match the plant by tier, regulator, age band and year "
                                f"({cells} cells; tightest {worst[1]})")
S = pd.concat(sev_rows)
cv = math.sqrt(math.exp(P["benefits"]["OP"]["sev_sigma"] ** 2) - 1)
worst = (0.0, "")
for fac in ("tier", "year"):
    g = S.groupby(fac)
    for k, grp in g:
        if len(grp) < 200:
            continue
        r = grp["x"].sum() / grp["mu"].sum()
        tol = 4 * cv / math.sqrt(len(grp)) + 0.02
        if abs(r - 1) / tol > worst[0]:
            worst = (abs(r - 1) / tol, f"{fac} {k} ratio {r:.3f}")
ok(worst[0] < 1, f"outpatient severity matches the plant by tier and year, incl. 6% trend (tightest {worst[1]})")

# tier and regulator really are in the data (a model has something to find)
e = E[E.group == "OPall"].groupby("tier")["e"].sum()
o = O[O.group == "OPall"].groupby("tier").size()
ok(o.get("CN", 0) > 0 and o.get("VN", 0) > 0, "top and bottom tiers both present in the pool")
mix = pd.concat([pd.read_csv(d / x["code"] / "04_Outputs" / "csv" / "dim_life.csv", usecols=["TPA", "Network"])
                 .assign(code=x["code"]) for x in P["cedants"]])
mix["tier"] = [control.network_tier(t, n) for t, n in zip(mix["TPA"], mix["Network"])]
vn = mix.groupby("code")["tier"].apply(lambda s: round((s == "VN").mean(), 2))
ok(vn.nunique() > 2, "cedants differ in realised tier mix (confounding planted for the GLM to resolve)")
raw = mix["Network"].astype(str)
ok((raw != raw.str.upper()).any() and raw.str.endswith(" ").any(), "raw networks need case / space normalisation")

# ---------------------------------------------------------------- heterogeneity and tail
for code, t in truth["cedants"].items():
    ph = t["policyholder_effects"]
    if ph["n"] >= 100:
        ok(abs(ph["log_sd"] / P["heterogeneity"]["policyholder_sigma"] - 1) < 0.25,
           f"{code} policyholder effect spread ~ planted ({ph['log_sd']:.3f}, n={ph['n']})")
tail = dict(P)
tail["large_loss"] = dict(P["large_loss"], rate_per_1000_ly=40.0)
tail["cedants"] = P["cedants"][:3]
dt_ = tmpdir('t_')
synth.generate(dt_, plant=tail, scale=0.1, progress=lambda m: None)
xs = pd.concat([pd.read_csv(dt_ / x["code"] / "04_Outputs" / "csv" / "fact_claims.csv", usecols=["PayerShare", "FOB"])
                for x in tail["cedants"]])
u, cap = P["large_loss"]["threshold"], P["large_loss"]["cap"]
x = xs[(xs.FOB == "In-Patient") & (xs.PayerShare >= u) & (xs.PayerShare < cap)]["PayerShare"].values
alpha = len(x) / np.log(x / u).sum()
se = alpha / math.sqrt(len(x))
ok(len(x) > 100 and abs(alpha - P["large_loss"]["pareto_alpha"]) < 3 * se,
   f"Pareto tail recovered: alpha {alpha:.2f} vs planted {P['large_loss']['pareto_alpha']} (n={len(x)}, se {se:.2f})")

# ---------------------------------------------------------------- members
dim = pd.read_csv(d / "C01" / "04_Outputs" / "csv" / "dim_life.csv", usecols=["MemKey", "Member DOB", "AgeAtInception"])
ok(dim.groupby("MemKey")["Member DOB"].nunique().max() == 1, "a member keeps one date of birth across years")
ok(dim["AgeAtInception"].min() >= 0, "no negative ages")
fc = pd.read_csv(d / "C01" / "04_Outputs" / "csv" / "fact_claims.csv", usecols=["FOB", "Claimed", "BeneficiaryShare"])
opd = fc[fc.FOB == "Dental"]
ok(abs((opd.BeneficiaryShare / opd.Claimed).median() - P["benefits"]["Dental"]["copay"]) < 0.001,
   "co-pay is the planted share of the claimed amount")
done("test_synth")
