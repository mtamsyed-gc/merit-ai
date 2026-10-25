"""Synthetic pool generator: fictitious cedants written as Merit run folders, with planted effects.

Each cedant's folder is shaped like a Merit v7 run (04_Outputs/csv/<table>.csv) and conforms to the pinned
contract. Claims are drawn from exactly the model in synth/plant.json; the realised draws go to truth.json so
tests can check the generator (A/E on the draws) and later models can be checked against the plant (G4.1).

Determinism: one numpy SeedSequence per cedant from (seed, cedant index); same plant + seed + scale =
byte-identical files.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import ROOT, VERSION
from . import contract as K
from . import control

PLANT_PATH = ROOT / "synth" / "plant.json"
AGE_BANDS = [(0, "00-01"), (2, "02-18"), (19, "19-25"), (26, "26-35"), (36, "36-50"), (51, "51-60"), (61, "61+")]
GROUP_BANDS = [(0, "0-4"), (5, "5-20"), (21, "21-50"), (51, "51-150"), (151, "151-200"), (201, "201-500"),
               (501, "501-750"), (751, "751-1000"), (1001, "1001-1500"), (1501, "1501+")]
ICD_CHAPTER = {"A": "A00-B99 Certain infectious and parasitic diseases", "C": "C00-D49 Neoplasms",
               "E": "E00-E89 Endocrine, nutritional and metabolic diseases",
               "H": "H00-H59 Diseases of the eye and adnexa", "I": "I00-I99 Diseases of the circulatory system",
               "J": "J00-J99 Diseases of the respiratory system", "K": "K00-K95 Diseases of the digestive system",
               "M": "M00-M99 Diseases of the musculoskeletal system and connective tissue",
               "O": "O00-O9A Pregnancy, childbirth and the puerperium",
               "R": "R00-R99 Symptoms, signs and abnormal clinical and laboratory findings, not elsewhere classified",
               "S": "S00-T88 Injury, poisoning and certain other consequences of external causes",
               "Z": "Z00-Z99 Factors influencing health status and contact with health services"}
PROVIDER_REGION = {"DHA": ("Dubai", "DXB"), "DOH": ("Abu Dhabi", "AUH"), "MOHAP": ("Sharjah", "NE")}
DAY = np.timedelta64(1, "D")


def load_plant(path=None):
    return json.loads(Path(path or PLANT_PATH).read_text(encoding="utf-8"))


def _band(x, bands):
    out = np.empty(len(x), dtype=object)
    for lo, lab in bands:
        out[x >= lo] = lab
    return out


def _midx(d):
    """Month index (year * 12 + month - 1) of datetime64[D] values."""
    m = d.astype("datetime64[M]").astype(np.int64)
    return m + 1970 * 12


def _mstart(mi):
    return (np.asarray(mi, dtype=np.int64) - 1970 * 12).astype("datetime64[M]").astype("datetime64[D]")


def _dstr(d):
    return np.datetime_as_string(d, unit="D")


def _reverse_networks():
    """tier -> first raw network name per TPA, from the crosswalk (the generator writes raw names)."""
    rev = {}
    for tpa, m in control.load("crosswalk")["network"]["by_tpa"].items():
        r = {}
        for raw, tier in m.items():
            r.setdefault(tier, raw)
        rev[tpa] = r
    return rev


# --------------------------------------------------------------------------------------------------------------
# book: policies and members by UW year
# --------------------------------------------------------------------------------------------------------------
def _book(c, ci, P, rng, scale, rev):
    """Life-periods of one cedant as a dict of numpy arrays."""
    D, M = P["dates"], P["members"]
    V = np.datetime64(D["valuation_date"])
    uwys = D["uw_years"]
    tpas, tpa_p = list(c["tpas"]), np.array(list(c["tpas"].values()), float)
    regs, reg_p = list(c["regulators"]), np.array(list(c["regulators"].values()), float)
    nat, nat_p = P["nationality"]["values"], np.array(P["nationality"]["p"], float)
    het = P["heterogeneity"]
    pol_sig = het["policyholder_sigma"]

    rows = {k: [] for k in ("pol", "mc", "tpa", "tier", "reg", "ptype", "polfx", "uwy", "pstart", "pend",
                            "mem", "rel", "gender", "dob", "nat", "cs", "ce", "joiner", "leaver", "tenure", "newren",
                            "gsize")}
    policies = []     # live master contracts: dict
    mem_seq = [0]
    pol_seq = [0]

    def new_member(rel, rng):
        mem_seq[0] += 1
        if rel == "Principal":
            g = "Male" if rng.random() < M["principal_male"] else "Female"
            age = int(np.clip(rng.normal(36, 9), 19, 64))
        elif rel == "Spouse":
            g = "Female" if rng.random() < 0.8 else "Male"
            age = int(np.clip(rng.normal(33, 7), 19, 60))
        else:
            g = "Male" if rng.random() < 0.5 else "Female"
            age = int(rng.integers(0, 19))
        dob = np.datetime64(f"{2022 - age}-01-01") + int(rng.integers(0, 365)) * DAY   # fixed per member
        return {"mem": f"{c['code']}M{mem_seq[0]:06d}", "rel": "Principal" if rel == "Principal" else "Dependant",
                "gender": g, "age2023": age, "dob": dob, "nat": nat[rng.choice(len(nat), p=nat_p / nat_p.sum())]}

    def members_for(size, rng):
        n_pr = max(1, int(round(size / (1 + M["dependants_per_principal"]))))
        out = [new_member("Principal", rng) for _ in range(n_pr)]
        n_dep = max(0, size - n_pr)
        for _ in range(n_dep):
            out.append(new_member("Spouse" if rng.random() < M["spouse_share_of_dependants"] else "Child", rng))
        return out

    def new_policy(uwy, rng):
        pol_seq[0] += 1
        tpa = tpas[rng.choice(len(tpas), p=tpa_p / tpa_p.sum())]
        avail = [t for t in c["tiers"] if t in rev[tpa]]
        tp = np.array([c["tiers"][t] for t in avail], float)
        tier = avail[rng.choice(len(avail), p=tp / tp.sum())]
        reg = regs[rng.choice(len(regs), p=reg_p / reg_p.sum())]
        sme = rng.random() < c["sme_share"]
        mu, sd = M["policy_size_lognormal"]
        size = int(np.clip(np.exp(rng.normal(mu, sd)), M["policy_size_min"], M["policy_size_max"]))
        size = min(size, 250) if sme else max(size, 20)
        month = int(rng.integers(1, 13))
        return {"pol": f"{c['code']}P{pol_seq[0]:05d}", "mc": f"{c['code']}MC{pol_seq[0]:05d}", "tpa": tpa,
                "tier": tier, "reg": reg, "ptype": "SME" if sme else "GROUP",
                "polfx": float(np.exp(rng.normal(-pol_sig ** 2 / 2, pol_sig))), "month": month,
                "first_uwy": uwy, "members": members_for(size, rng), "target": size}

    for k, uwy in enumerate(uwys):
        target = c["lives_2023"] * scale * (1 + c["growth"]) ** k
        nxt = []
        for p in policies:                                 # renewals
            if rng.random() >= M["policy_renewal"]:
                continue
            kept = [m for m in p["members"] if rng.random() < M["member_retention"]]
            grow = int(round(p["target"] * (1 + c["growth"] + rng.normal(0, 0.05))))
            p["target"] = max(2, grow)
            add = max(0, p["target"] - len(kept))
            kept += members_for(add, rng) if add else []
            p["members"] = kept
            p["renewal"] = True
            nxt.append(p)
        lives = sum(len(p["members"]) for p in nxt)
        while lives < target:
            p = new_policy(uwy, rng)
            p["renewal"] = False
            nxt.append(p)
            lives += len(p["members"])
        policies = nxt
        for p in policies:
            ps = np.datetime64(f"{uwy}-{p['month']:02d}-01")
            if ps > V:                                     # not yet written at the valuation date
                continue
            pe = (np.datetime64(f"{uwy + 1}-{p['month']:02d}-01") - DAY)
            ndays = int((pe - ps) / DAY) + 1
            gsize = len(p["members"])
            for m in p["members"]:
                cs, ce = ps, pe
                j = l = 0
                if rng.random() < M["joiner_share"]:
                    cs = ps + int(rng.integers(1, ndays - 30)) * DAY
                    j = 1
                if rng.random() < M["leaver_share"]:
                    span = int((pe - cs) / DAY)
                    if span > 30:
                        ce = cs + int(rng.integers(30, span)) * DAY
                        l = 1
                if cs > V:                                 # member starts after the valuation date
                    continue
                dob = m["dob"]
                for key, val in (("pol", p["pol"]), ("mc", p["mc"]), ("tpa", p["tpa"]), ("tier", p["tier"]),
                                 ("reg", p["reg"]), ("ptype", p["ptype"]), ("polfx", p["polfx"]), ("uwy", uwy),
                                 ("pstart", ps), ("pend", pe), ("mem", m["mem"]), ("rel", m["rel"]),
                                 ("gender", m["gender"]), ("dob", dob), ("nat", m["nat"]), ("cs", cs), ("ce", ce),
                                 ("joiner", j), ("leaver", l), ("tenure", uwy - p["first_uwy"]),
                                 ("newren", "Renewal" if p["renewal"] else "New"), ("gsize", gsize)):
                    rows[key].append(val)
    out = {k: np.array(v) for k, v in rows.items()}
    for k in ("pstart", "pend", "dob", "cs", "ce"):
        out[k] = out[k].astype("datetime64[D]")
    return out


# --------------------------------------------------------------------------------------------------------------
def _years(d, base):
    return (d - base) / DAY / 365.25


def _expected_rates(L, P, ci, ced_fx):
    """Per life-period frequency multipliers by benefit (no trend, season or exposure)."""
    fr = P["freq_rel"]
    age = L["ageband"]
    out = {}
    for b in P["benefits"]:
        excl = set(P["rel_excludes"].get(b, []))
        r = np.full(len(age), P["benefits"][b]["freq"], float)
        if "age_band" not in excl:
            r *= np.array([fr["age_band"][a] for a in age])
        if "gender" not in excl:
            r *= np.array([fr["gender"][g] for g in L["gender"]])
        r *= np.array([fr["tier"][t] for t in L["tier"]])
        r *= np.array([fr["regulator"][g] for g in L["reg"]])
        r *= np.array([fr["policy_type"][t] for t in L["ptype"]])
        r *= ced_fx * L["polfx"]
        elig = P["benefits"][b].get("eligible")
        if elig:
            r *= (L["ggroup"] == elig)
        out[b] = r
    return out


def _sev_rel(L, P):
    sr = P["sev_rel"]
    return np.array([sr["tier"][t] for t in L["tier"]]) * np.array([sr["regulator"][g] for g in L["reg"]])


def _cdf(pmf, n=13):
    c = np.cumsum(pmf)
    out = np.ones(n)
    out[:len(c)] = np.minimum(c, 1.0)
    return out


def _conv(a, b):
    return np.convolve(a, b)


def _write(df, path, cols):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: generator did not build columns {missing}")
    path.parent.mkdir(parents=True, exist_ok=True)
    df = df.reindex(columns=cols)
    df.to_csv(path, index=False, lineterminator="\n", na_rep="")


def _round(df, cols, nd):
    for c in cols:
        df[c] = df[c].astype(float).round(nd)


def generate(out_dir, plant=None, seed=None, scale=0.1, stamp_contract=True, progress=print, overwrite=False):
    """Write a synthetic pool pack to out_dir and return its truth dict. out_dir must be empty or absent unless
    overwrite=True (then it is cleared first), so no stale cedant folder survives."""
    P = plant or load_plant()
    seed = P["seed"] if seed is None else seed
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(f"{out_dir} is not empty; pass overwrite=True to replace it")
        import shutil
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pin, contract = K.load_pin()
    cols = {t: [c for c, _ in K.columns(contract, t)] for t in K.MAIN_TABLES}
    rev = _reverse_networks()
    D = P["dates"]
    V = np.datetime64(D["valuation_date"])
    X = np.datetime64(D["claims_extract_date"])
    vi, xi = int(_midx(np.array([V]))[0]), int(_midx(np.array([X]))[0])
    base = np.datetime64(D["trend_base_date"])
    season = np.array(P["seasonality"], float)
    season = season / season.mean()
    tr = P["trend"]
    LL = P["large_loss"]
    het = P["heterogeneity"]
    paid_pmf = np.array(P["reporting"]["paid_lag_pmf"], float)
    truth = {"plant_version": P["version"], "generator_version": VERSION, "seed": seed, "scale": scale,
             "contract_version": pin["version"], "valuation_date": D["valuation_date"],
             "claims_extract_date": D["claims_extract_date"], "cedants": {}, "ae": {}, "cf_truth": {},
             "files": {}}
    ae = {}  # (benefit, factor, level) -> [expected, drawn]

    for ci, c in enumerate(P["cedants"]):
        rng = np.random.default_rng(np.random.SeedSequence([seed, ci]))
        ced_fx = float(np.exp(rng.normal(-het["cedant_sigma"] ** 2 / 2, het["cedant_sigma"])))
        lr_lo, lr_hi = P["premium"]["loss_ratio_target_range"]
        lr_target = float(rng.uniform(lr_lo, lr_hi))
        L = _book(c, ci, P, rng, scale, rev)
        n = len(L["mem"])
        progress(f"  {c['code']}: {n:,} life-periods")
        L["age"] = ((L["cs"] - L["dob"]) / DAY / 365.25).astype(int)
        L["ageband"] = _band(L["age"], AGE_BANDS)
        L["ggroup"] = np.where((L["gender"] == "Female") & (L["age"] >= 18) & (L["age"] <= 45),
                               "Maternity Eligible Female", L["gender"])
        abd = ((L["pend"] - L["pstart"]) / DAY).astype(int) + 1
        covdays = ((L["ce"] - L["cs"]) / DAY).astype(int) + 1
        ee = np.minimum(L["ce"], V)
        earned = np.maximum(0, ((ee - L["cs"]) / DAY).astype(int) + 1)
        rates = _expected_rates(L, P, ci, ced_fx)
        sevr = _sev_rel(L, P)
        # expected annual cost per LY at the period midpoint, for premium
        mid = L["cs"] + (covdays // 2) * DAY
        t_mid = _years(mid, base)
        exp_cost = np.zeros(n)
        hidden = ced_fx * L["polfx"]       # cedant / policyholder effects are not known to the rate manual
        for b, r in rates.items():
            B = P["benefits"][b]
            exp_cost += r / hidden * (1 + tr["freq_pa"]) ** t_mid * B["sev_mean"] * sevr * (1 + tr["sev_pa"]) ** t_mid
        exp_cost += LL["rate_per_1000_ly"] / 1000 * LL["threshold"] * LL["pareto_alpha"] / (LL["pareto_alpha"] - 1)
        gross = np.round(exp_cost * covdays / abd / lr_target * np.exp(rng.normal(0, 0.05, n)), 2)
        net = np.round(gross * P["premium"]["net_to_gross"], 2)

        # ---------------- member-month fan (exposure to the valuation date)
        live = earned > 0
        idx = np.nonzero(live)[0]
        m0 = _midx(L["cs"][idx])
        m1 = _midx(ee[idx])
        nm = (m1 - m0 + 1).astype(int)
        r_i = np.repeat(idx, nm)
        off = np.arange(nm.sum()) - np.repeat(np.cumsum(nm) - nm, nm)
        mm = np.repeat(m0, nm) + off
        ms = _mstart(mm)
        me = _mstart(mm + 1) - DAY
        lo = np.maximum(ms, L["cs"][r_i])
        hi = np.minimum(me, ee[r_i])
        days = ((hi - lo) / DAY).astype(int) + 1
        ly = days / abd[r_i]
        cs_m = _midx(L["cs"])
        first = mm == cs_m[r_i]
        fmm = pd.DataFrame({
            "r": r_i, "MonthStart": _dstr(ms), "EarnedDays": days, "EarnedLY_Gross": ly, "EarnedLY_Net": ly,
            "EarnedPrem_Gross": gross[r_i] * days / covdays[r_i], "EarnedPrem_Net": net[r_i] * days / covdays[r_i],
            "WrittenPrem_Gross": np.where(first, gross[r_i], 0.0), "WrittenPrem_Net": np.where(first, net[r_i], 0.0),
            "WrittenLY_Gross": np.where(first, covdays[r_i] / abd[r_i], 0.0),
            "WrittenLY_Net": np.where(first, covdays[r_i] / abd[r_i], 0.0)})

        # ---------------- claims draws on member-months
        t_m = _years(ms + 14 * DAY, base)
        seas = season[(mm % 12).astype(int)]
        lines = []
        for b, r in rates.items():
            B = P["benefits"][b]
            lam = r[r_i] * ly * (1 + tr["freq_pa"]) ** t_m * seas
            cnt = rng.poisson(lam)
            for fac, lev in (("tier", L["tier"][r_i]), ("age_band", L["ageband"][r_i]), ("regulator", L["reg"][r_i]),
                             ("cedant", np.full(len(r_i), c["code"])), ("all", np.full(len(r_i), "all"))):
                for v in np.unique(lev):
                    sel = lev == v
                    a = ae.setdefault(f"{b}|{fac}|{v}", [0.0, 0])
                    a[0] += float(lam[sel].sum())
                    a[1] += int(cnt[sel].sum())
            k = np.repeat(np.arange(len(r_i)), cnt)
            if not len(k):
                continue
            mean = B["sev_mean"] * sevr[r_i[k]] * (1 + tr["sev_pa"]) ** t_m[k]
            sig = B["sev_sigma"]
            amt = np.exp(rng.normal(np.log(mean) - sig ** 2 / 2, sig))
            fob = np.full(len(k), B["fob"], dtype=object)
            if b == "OP":
                u = rng.random(len(k))
                acc = 0.0
                for f, s in P["unmapped_fob_share"].items():
                    fob[(u >= acc) & (u < acc + s)] = f
                    acc += s
            ptypes = np.array(B["provider"], dtype=object)[rng.choice(len(B["provider"]), size=len(k),
                                                                        p=B["provider_p"])]
            icd = np.array(B["icd"], dtype=object)[rng.integers(0, len(B["icd"]), len(k))]
            lines.append({"m": k, "benefit": np.full(len(k), b, dtype=object), "amt": amt, "fob": fob,
                          "ptype": ptypes, "icd": icd, "copay": np.full(len(k), B["copay"]), "large": np.zeros(len(k), int)})
        # large losses: one IP line per event, Pareto above the threshold, untrended
        lamL = LL["rate_per_1000_ly"] / 1000 * ly
        cntL = rng.poisson(lamL)
        kL = np.repeat(np.arange(len(r_i)), cntL)
        sevL = np.minimum(LL["threshold"] * (1 - rng.random(len(kL))) ** (-1 / LL["pareto_alpha"]), LL["cap"])
        aL = ae.setdefault(f"Large|all|all", [0.0, 0])
        aL[0] += float(lamL.sum())
        aL[1] += int(cntL.sum())
        if len(kL):
            BL = P["benefits"][LL["benefit"]]
            lines.append({"m": kL, "benefit": np.full(len(kL), "Large", dtype=object), "amt": sevL,
                          "fob": np.full(len(kL), BL["fob"], dtype=object),
                          "ptype": np.full(len(kL), "Hospital", dtype=object),
                          "icd": np.array(BL["icd"], dtype=object)[rng.integers(0, len(BL["icd"]), len(kL))],
                          "copay": np.zeros(len(kL)), "large": np.ones(len(kL), int)})
        C = {k2: np.concatenate([x[k2] for x in lines]) for k2 in lines[0]}
        k = C["m"]
        nL = len(k)
        rr = r_i[k]
        tday = lo[k] + (rng.random(nL) * days[k]).astype(int) * DAY
        inc = _midx(tday)
        tpa_l = L["tpa"][rr]
        rep_lag = np.zeros(nL, int)
        for t in np.unique(tpa_l):
            pmf = np.array(P["reporting"]["report_lag_pmf"][t], float)
            sel = tpa_l == t
            rep_lag[sel] = rng.choice(len(pmf), size=int(sel.sum()), p=pmf / pmf.sum())
        pay_lag = rng.choice(len(paid_pmf), size=nL, p=paid_pmf / paid_pmf.sum())
        rep_m = inc + rep_lag
        reported = rep_m <= xi
        paid = reported & (rep_m + pay_lag <= xi)
        mr = c["match_rate"]
        matched = reported & (rng.random(nL) < mr)
        amt = np.round(C["amt"], 2)
        devlag = xi - inc
        cf = {}
        for t in np.unique(L["tpa"]):
            pmf = np.array(P["reporting"]["report_lag_pmf"][t], float)
            cfr = _cdf(pmf)
            cfp = _cdf(_conv(pmf, paid_pmf))
            cf[t] = (cfr, cfp)
            truth["cf_truth"][t] = {"IBNR": [round(float(x), 10) for x in cfr],
                                    "IBNP": [round(float(x), 10) for x in cfp]}
        cf_r = np.ones(nL)
        cf_p = np.ones(nL)
        for t in np.unique(tpa_l):
            sel = tpa_l == t
            dl = np.minimum(devlag[sel], 12)
            cf_r[sel] = cf[t][0][dl]
            cf_p[sel] = cf[t][1][dl]

        # ---------------- tables
        code = c["code"]
        payer = c["name"]
        life_key = np.array([f"{payer}|{t}|{p}|{m}" for t, p, m in zip(L["tpa"], L["pol"], L["mem"])], dtype=object)
        order = pd.DataFrame({"k": life_key, "u": L["uwy"]}).sort_values(["k", "u"], kind="mergesort").index.values
        life_id = np.empty(n, int)
        life_id[order] = np.arange(1, n + 1)
        # raw network values as a TPA file might spell them (mixed case, stray spaces): the crosswalk must normalise
        net_raw = np.array([rev[t][tier].title() + (" " if u < 0.1 else "")
                            for t, tier, u in zip(L["tpa"], L["tier"], rng.random(n))], dtype=object)
        groups = P["nationality"]["groups"]
        dim = pd.DataFrame({
            "LifeID": life_id, "LifeKey": life_key, "Payer Name": payer, "Risk Carrier": payer,
            "MasterCedantName": payer, "TPA": L["tpa"], "PolKey": L["pol"], "MemKey": L["mem"], "UWY": L["uwy"],
            "PolicyStart": _dstr(L["pstart"]), "PolicyEndAdj": _dstr(L["pend"]), "AnnualBasisDays": abd,
            "CovStart": _dstr(L["cs"]), "CovEnd": _dstr(L["ce"]), "Periods": 1, "CovDays": covdays,
            "EarnedDays": earned, "ZP_Gross": 1, "ZP_Net": 1,
            "WrittenLY_Gross": covdays / abd, "WrittenLY_Net": covdays / abd,
            "EarnedLY_Gross": earned / abd, "EarnedLY_Net": earned / abd,
            "WrittenPrem_Gross": gross, "WrittenPrem_Net": net,
            "EarnedPrem_Gross": gross * np.minimum(earned, covdays) / covdays,
            "EarnedPrem_Net": net * np.minimum(earned, covdays) / covdays,
            "RI Name": "SYNTH-RE", "Policy Type": L["ptype"], "PolicyTypeUsed": L["ptype"],
            "PolicyTypeSource": "raw", "Master Contract ID": L["mc"],
            "Contract Name": np.char.add("Synthetic group ", L["mc"].astype(str)),
            "Relation": L["rel"], "Gender": L["gender"], "Marital Status": "Not Available",
            "Nationality": L["nat"], "Region": [P["region_raw"][g] for g in L["reg"]], "Network": net_raw,
            "Plan / Category": "", "Member DOB": _dstr(L["dob"]), "AgeAtInception": L["age"],
            "AgeBand": L["ageband"], "GroupSize": L["gsize"], "GroupSizeBand": _band(L["gsize"], GROUP_BANDS),
            "NewRenewal": L["newren"], "NewRenewalSource": "synthetic", "Joiner": L["joiner"],
            "Leaver": L["leaver"], "Tenure": L["tenure"], "Currency": "AED", "Country": "UAE",
            "EndoGroup": "Initial/Renewal in force", "EndoPath": "", "VoidPeriods": 0, "OverlapVoidPeriods": 0,
            "ReinstatedPeriods": 0, "MemberReactPeriods": 0,
            "Region Group": [P["region_group_raw"][g] for g in L["reg"]],
            "Nationality Group": [groups[x] for x in L["nat"]], "Gender Group": L["ggroup"],
            "Distribution": "Direct"})
        _round(dim, ["WrittenLY_Gross", "WrittenLY_Net", "EarnedLY_Gross", "EarnedLY_Net"], 6)
        _round(dim, ["EarnedPrem_Gross", "EarnedPrem_Net"], 6)
        dim = dim.iloc[order]

        fmm["LifeID"] = life_id[fmm["r"]]
        fmm["LifeKey"] = life_key[fmm["r"]]
        fmm["UWY"] = L["uwy"][fmm["r"]]
        fmm["Payer Name"] = payer
        fmm["TPA"] = L["tpa"][fmm["r"]]
        _round(fmm, ["EarnedLY_Gross", "EarnedLY_Net", "WrittenLY_Gross", "WrittenLY_Net"], 6)
        _round(fmm, ["EarnedPrem_Gross", "EarnedPrem_Net", "WrittenPrem_Gross", "WrittenPrem_Net"], 6)
        fmm = fmm.sort_values(["LifeID", "MonthStart"], kind="mergesort")

        keep = matched
        kk = np.nonzero(keep)[0]
        rk = rr[kk]
        cop = np.round(amt[kk] * C["copay"][kk] / (1 - C["copay"][kk]), 2)   # co-pay share of the claimed amount
        is_paid = paid[kk]
        reg_l = L["reg"][rk]
        prov_reg = np.array([PROVIDER_REGION[g][0] for g in reg_l], dtype=object)
        prov_grp = np.array([PROVIDER_REGION[g][1] for g in reg_l], dtype=object)
        prov_no = rng.integers(1, 21, len(kk))
        prov = np.array([f"SYN {pt} {g} {i:02d}" for pt, g, i in zip(C["ptype"][kk], prov_grp, prov_no)], dtype=object)
        icd = C["icd"][kk]
        chapter = np.array([ICD_CHAPTER[x[0]] for x in icd], dtype=object)
        claim_no = np.arange(1, len(kk) + 1)
        ckey = np.array([f"{code}C{i:08d}" for i in claim_no], dtype=object)
        inc_d = _mstart(inc[kk])
        rep_d = _mstart(rep_m[kk])
        paid_d = np.where(is_paid, _dstr(_mstart(rep_m[kk] + pay_lag[kk])), "")
        pshare = amt[kk]
        fc = pd.DataFrame({
            "ClaimKey": ckey, "Payer Name": payer, "TPA": tpa_l[kk], "UWY": L["uwy"][rk], "LifeKey": life_key[rk],
            "LifeID": life_id[rk], "PolKey": L["pol"][rk], "MemKey": L["mem"][rk],
            "ClaimID": np.char.add(np.char.add(tpa_l[kk].astype(str), "|"), ckey.astype(str)),
            "ClaimantKey": life_key[rk], "MatchTier": "T1 policy + member, in cover", "MatchStatus": "Matched",
            "InCover": 1, "InExperience": 1, "StatusClass": np.where(is_paid, "Paid", "Outstanding"),
            "Claim Type": np.where(is_paid, "Paid", "Outstanding"), "FOB": C["fob"][kk],
            "FOC": np.where(C["benefit"][kk] == "Maternity", "Maternity", "Physical Illness"),
            "ICD Code": icd, "ICD Description": "", "ICD Chapter": chapter, "Provider Name": prov,
            "Provider Type": C["ptype"][kk], "Provider Region": prov_reg, "TreatmentDate": _dstr(tday[kk]),
            "IncurredMonth": _dstr(inc_d), "ReportedMonth": _dstr(rep_d), "PaidMonth": paid_d,
            "RepLag": rep_lag[kk], "PaidLag": np.where(is_paid, rep_lag[kk] + pay_lag[kk], -1),
            "Claimed": np.round(pshare + cop, 2), "Declined": 0.0, "Discounts": 0.0,
            "Approved": np.round(pshare + cop, 2), "BeneficiaryShare": cop, "PayerShare": pshare,
            "Paid": np.where(is_paid, pshare, 0.0), "OS": np.where(is_paid, 0.0, pshare), "CountFlag": 1,
            "LargeFlag": (pshare >= 100000).astype(int), "SrcOrder": 1000000 + claim_no, "MasterCedantName": payer,
            "RI Name": "SYNTH-RE", "DevLag": devlag[kk], "CF_Basis": "IBNR",
            "CF_Amount": np.round(cf_r[kk], 10), "CF_Count": np.round(cf_r[kk], 10),
            "UltimateAmount": np.round(pshare / cf_r[kk], 2), "UltimateCount": np.round(1 / cf_r[kk], 10),
            "Provider Region Group": prov_grp, "CF_Basis_IBNP": "IBNP",
            "CF_Amount_IBNP": np.round(cf_p[kk], 10), "CF_Count_IBNP": np.round(cf_p[kk], 10),
            "UltimateAmount_IBNP": np.round(np.where(is_paid, pshare, 0.0) / cf_p[kk], 2),
            "UltimateCount_IBNP": np.round(np.where(is_paid, 1.0, 0.0) / cf_p[kk], 10)})
        fc["PaidLag"] = fc["PaidLag"].astype(object).where(fc["PaidLag"] >= 0, "")

        fc["_paid"] = (fc["StatusClass"] == "Paid").astype(float)
        g = fc.groupby(["Payer Name", "TPA", "IncurredMonth", "UWY"], sort=True)
        ult = g.agg(Lag=("DevLag", "first"), CF_Used=("CF_Amount", "first"), CF_Count_Used=("CF_Count", "first"),
                    Reported=("PayerShare", "sum"), Paid=("Paid", "sum"), OS=("OS", "sum"),
                    Ultimate=("UltimateAmount", "sum"), ReportedCount=("CountFlag", "sum"),
                    UltimateCount=("UltimateCount", "sum"), CF_Used_IBNP=("CF_Amount_IBNP", "first"),
                    CF_Count_Used_IBNP=("CF_Count_IBNP", "first"), Ultimate_IBNP=("UltimateAmount_IBNP", "sum"),
                    UltimateCount_IBNP=("UltimateCount_IBNP", "sum"), PaidCount=("_paid", "sum")).reset_index()
        ult["IBNR"] = ult["Ultimate"] - ult["Reported"]
        ult["IBNP"] = ult["Ultimate_IBNP"] - ult["Paid"]
        ult["Method"] = "IBNR"
        ult["CF_Basis"] = "IBNR"
        ult["CF_Basis_IBNP"] = "IBNP"
        _round(ult, ["Reported", "Paid", "OS", "Ultimate", "IBNR", "Ultimate_IBNP", "IBNP"], 2)
        _round(ult, ["UltimateCount", "UltimateCount_IBNP"], 6)

        cfs = []
        for t in sorted(cf):
            for basis, arr in (("IBNR", cf[t][0]), ("IBNP", cf[t][1])):
                for meas in ("Amount", "Count"):
                    for lag in range(13):
                        cfs.append({"TPA": t, "Basis": basis, "Measure": meas, "Lag": lag, "CF_Derived": "",
                                    "CF_Override": "", "CF_Used": round(float(arr[lag]), 10),
                                    "Source": "synthetic truth", "Credible": 1, "Cohorts": "", "Claims": ""})
        cfsel = pd.DataFrame(cfs)

        run = out_dir / code / "04_Outputs" / "csv"
        _write(dim, run / "dim_life.csv", cols["dim_life"])
        _write(fmm, run / "fact_member_month.csv", cols["fact_member_month"])
        _write(fc, run / "fact_claims.csv", cols["fact_claims"])
        _write(cfsel, run / "cf_selected.csv", cols["cf_selected"])
        _write(ult, run / "ultimates.csv", cols["ultimates"])

        # recon, exceptions, manifests
        rp = []
        for t in sorted(np.unique(L["tpa"])):
            d = dim[dim["TPA"] == t]
            f = fmm[fmm["TPA"] == t]
            vals = {"rows_in": len(d), "life_periods": len(d), "rows_unmapped": 0, "rows_ignored": 0,
                    "rows_missing": 0, "rows_duplicate": 0, "rows_excluded": 0, "rows_overlap": 0}
            for b in ("Gross", "Net"):
                for mz in ("WrittenPrem", "EarnedPrem", "WrittenLY", "EarnedLY"):
                    vals[f"{mz}_{b}"] = round(float(d[f"{mz}_{b}"].sum()), 6)
                    vals[f"FanDiff_{mz}_{b}"] = round(float(f[f"{mz}_{b}"].sum() - d[f"{mz}_{b}"].sum()), 6)
            for k2 in sorted(vals):
                rp.append({"TPA": t, "Measure": k2, "Value": float(vals[k2])})
        _write(pd.DataFrame(rp), run / "recon_premium.csv", ["TPA", "Measure", "Value"])
        rc = []
        for t in sorted(np.unique(L["tpa"])):
            sel = (tpa_l == t) & reported
            m_ = sel & matched
            u_ = sel & ~matched
            ps_in = float(amt[sel].sum())
            ms_ = float(amt[m_].sum())
            rc.append({"TPA": t, "claim_lines_in": int(sel.sum()), "payer_share_in": round(ps_in, 2),
                       "paid_in": round(float(amt[sel & paid].sum()), 2),
                       "os_in": round(float(amt[sel & ~paid].sum()), 2), "no_treatment_date": 0,
                       "claims_after_valuation": 0, "payer_share_experience": round(ps_in, 2),
                       "matched_lines": int(m_.sum()), "member_date_lines": 0, "out_of_cover_lines": 0,
                       "ambiguous_lines": 0, "unmatched_lines": int(u_.sum()), "matched_share": round(ms_, 2),
                       "match_rate_amount": round(ms_ / ps_in, 6) if ps_in else 0.0,
                       "visits_counted": int(m_.sum()),
                       "ultimate_experience": round(float((amt[m_] / cf_r[m_]).sum()), 2),
                       "excluded_pre_inception": 0, "excluded_unmatched": int(u_.sum()),
                       "excluded_paid": round(float(amt[u_ & paid].sum()), 2),
                       "excluded_paid_os": round(float(amt[u_].sum()), 2)})
        recon_cols = ["TPA", "claim_lines_in", "payer_share_in", "paid_in", "os_in", "no_treatment_date",
                      "claims_after_valuation", "payer_share_experience", "matched_lines", "member_date_lines",
                      "out_of_cover_lines", "ambiguous_lines", "unmatched_lines", "matched_share",
                      "match_rate_amount", "visits_counted", "ultimate_experience", "excluded_pre_inception",
                      "excluded_unmatched", "excluded_paid", "excluded_paid_os"]
        _write(pd.DataFrame(rc), run / "recon_claims.csv", recon_cols)
        exc_cols = ["Code", "Severity", "TPA", "PolKey", "MemKey", "SrcOrder", "Message"]
        _write(pd.DataFrame([{"Code": "W-RI-TREATY", "Severity": "Flag", "TPA": sorted(c["tpas"])[0], "PolKey": "",
                              "MemKey": "", "SrcOrder": "", "Message": "synthetic: no treaty shares supplied"}]),
               run / "exceptions.csv", exc_cols)
        _write(pd.DataFrame(columns=exc_cols), run / "exceptions_claims.csv", exc_cols)
        manp = [("valuation_date", D["valuation_date"]), ("premium_extract_date", D["premium_extract_date"]),
                ("workflow", "Merit_02_Premium"), ("workflow_version", "SYNTH"), ("default_premium_basis", "Gross"),
                ("currency", "AED"), ("has_member_dob", "1")]
        if stamp_contract:              # Merit v7.3.2+ stamps both manifests (ete-dashboard TPA_RULES 74)
            manp.append(("contract_version", pin["version"]))
        _write(pd.DataFrame(manp, columns=["Key", "Value"]), run / "run_manifest_premium.csv", ["Key", "Value"])
        manc = [("valuation_date", D["valuation_date"]), ("claims_extract_date", D["claims_extract_date"]),
                ("claims_workflow", "Merit_03_Claims"), ("claims_workflow_version", "SYNTH"),
                ("large_claim_threshold", "100000"), ("has_claim_dob", "0"), ("has_paid_date", "1"),
                ("has_reported_date", "1"), ("has_icd", "1"), ("has_provider", "1"), ("has_fob", "1")]
        if stamp_contract:
            manc.append(("contract_version", pin["version"]))
        _write(pd.DataFrame(manc, columns=["Key", "Value"]), run / "run_manifest_claims.csv", ["Key", "Value"])

        truth["cedants"][code] = {
            "name": payer, "cedant_effect": round(ced_fx, 10), "loss_ratio_target": round(lr_target, 10),
            "match_rate_planted": mr, "life_periods": int(n), "earned_ly": round(float(dim["EarnedLY_Gross"].sum()), 6),
            "lines_drawn": int(nL), "lines_reported": int(reported.sum()), "lines_unreported": int((~reported).sum()),
            "lines_matched": int(matched.sum()), "lines_unmatched": int((reported & ~matched).sum()),
            "amount_drawn": round(float(amt.sum()), 2), "amount_matched": round(float(amt[matched].sum()), 2),
            "large_losses": int(len(kL)),
            "policyholder_effects": {"n": int(len(np.unique(L["mc"]))),
                                     "log_sd": round(float(np.std(np.log(np.unique(L["polfx"])))), 10),
                                     "by_master_contract": {mc: round(float(fx), 10) for mc, fx in
                                                            sorted(set(zip(L["mc"].tolist(), L["polfx"].tolist())))}}}

    truth["ae"] = {k: {"expected": round(v[0], 6), "drawn": v[1]} for k, v in sorted(ae.items())}
    for f in sorted(out_dir.rglob("*.csv")):
        truth["files"][f.relative_to(out_dir).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    (out_dir / "truth.json").write_text(json.dumps(truth, indent=1, sort_keys=True), encoding="utf-8")
    return truth
