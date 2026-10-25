"""Control files: load, validate, and look up (control/*.json)."""
import json
from functools import lru_cache

from . import ROOT

CONTROL_DIR = ROOT / "control"
FILES = ("gates", "thresholds", "crosswalk", "disclosure")
LEVELS = {"Stop", "Flag", "Info", "Auto"}


class ControlError(Exception):
    pass


@lru_cache(maxsize=None)
def load(name):
    if name not in FILES:
        raise ControlError(f"unknown control file {name}")
    return json.loads((CONTROL_DIR / f"{name}.json").read_text(encoding="utf-8"))


def checks():
    return {c["id"]: c for c in load("gates")["checks"]}


def threshold(check_id):
    return load("thresholds")["checks"].get(check_id, {})


def validate():
    """Problems found in the control files (empty list = valid)."""
    errs = []
    for n in FILES:
        if not load(n).get("version"):
            errs.append(f"{n}.json has no version")
    g = load("gates")
    ids = [c["id"] for c in g["checks"]]
    if len(ids) != len(set(ids)):
        errs.append("duplicate check ids in gates.json")
    for c in g["checks"]:
        for k in ("id", "gate", "phase", "on_fail", "title", "plain"):
            if not c.get(k):
                errs.append(f"{c.get('id')}: missing {k}")
        if c.get("gate") not in g["gates"]:
            errs.append(f"{c['id']}: gate {c.get('gate')} not declared")
        if c.get("on_fail") not in LEVELS:
            errs.append(f"{c['id']}: on_fail {c.get('on_fail')} not one of {sorted(LEVELS)}")
        if not c["id"].startswith(c["gate"] + "."):
            errs.append(f"{c['id']}: id does not belong to gate {c['gate']}")
    for cid in load("thresholds")["checks"]:
        if cid not in ids:
            errs.append(f"thresholds.json: {cid} is not a registered check")
    lvl = load("thresholds")["checks"].get("G1.1", {}).get("contract_version_missing_level")
    if lvl not in ("Stop", "Flag", "Info"):
        errs.append(f"thresholds G1.1 contract_version_missing_level {lvl!r} must be Stop, Flag or Info")
    net = load("crosswalk")["network"]
    tiers = set(net["tiers"])
    for tpa, m in net["by_tpa"].items():
        for raw, tier in m.items():
            if tier not in tiers:
                errs.append(f"crosswalk: {tpa} {raw} -> unknown tier {tier}")
            if raw != raw.strip().upper():
                errs.append(f"crosswalk: {tpa} {raw!r} must be trimmed upper case")
    for t in tiers:
        if t not in net["rollup"]:
            errs.append(f"crosswalk: tier {t} has no roll-up")
    for t, p in net.get("pooled_as", {}).items():
        if t not in tiers or p not in tiers:
            errs.append(f"crosswalk: pooled_as {t} -> {p} not both tiers")
    d = load("disclosure")
    for m, cls in d["measures"].items():
        if cls not in d["classes"]:
            errs.append(f"disclosure: measure {m} has unknown class {cls}")
    return errs


def network_tier(tpa, network):
    """Pool tier of a TPA's network value, or 'Unmapped'."""
    m = load("crosswalk")["network"]["by_tpa"].get(str(tpa or "").strip().upper(), {})
    return m.get(str(network or "").strip().upper(), "Unmapped")
