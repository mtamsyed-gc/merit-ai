"""Gate engine: runs a gate's checks on one subject, applies sign-offs, writes the gate report.

Statuses of a check result:
  PASS       the check passed
  STOP       failed a Stop check: the stream halts
  FLAG       failed a Flag check: continues only with a named sign-off
  INFO       recorded for the reader, never blocks
  AUTO       the stream acted automatically (roll-up, label); recorded, never blocks
  NOT_BUILT  the check is registered but its phase has not built it yet

Gate outcome: STOP if any STOP; else INCOMPLETE if any NOT_BUILT (unless allow_incomplete, which labels the
outcome "... (incomplete)"); else FLAG if any FLAG has no valid sign-off; else PASS.

A sign-off covers one finding: it names the check, the subject and the finding's fingerprint (a hash of the
check, subject, message and value shown in the report), and is signed in the gate's signer role. A changed
finding needs a new sign-off. Sign-offs apply to FLAG results only; a STOP can never be signed away.
"""
import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import VERSION
from . import control

REGISTRY = {}
STATUSES = {"PASS", "STOP", "FLAG", "INFO", "AUTO"}
ACTION = {"PASS": "Nothing to do.",
          "STOP": "Fix the cause shown, then re-run. A Stop cannot be signed off.",
          "FLAG": "Review the finding. Continue only after the named signer records a sign-off with a reason.",
          "INFO": "For information only.",
          "AUTO": "Handled automatically as described; nothing to do.",
          "NOT_BUILT": "This check is built in a later phase; the gate is not complete until it is."}


@dataclass
class Result:
    check_id: str
    status: str
    message: str
    value: object = None
    threshold: object = None
    details: list = field(default_factory=list)
    signed: dict = None
    subject: str = ""

    def fingerprint(self):
        raw = json.dumps([self.check_id, self.subject, self.message, str(self.value)], sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def check(check_id):
    """Register a check implementation. The function takes (ctx) and returns a Result."""
    def deco(fn):
        if check_id not in control.checks():
            raise ValueError(f"{check_id} is not registered in control/gates.json")
        REGISTRY[check_id] = fn
        return fn
    return deco


def fail_level(check_id):
    """Status a failure of this check takes (from gates.json on_fail)."""
    return {"Stop": "STOP", "Flag": "FLAG", "Info": "INFO", "Auto": "AUTO"}[control.checks()[check_id]["on_fail"]]


def _load_impl():
    from . import checks  # noqa: F401  (registers the built checks)


def built():
    _load_impl()
    return sorted(REGISTRY)


def load_signoffs(path):
    p = Path(path) if path else None
    if not p or not p.exists():
        return []
    rows = json.loads(p.read_text(encoding="utf-8"))
    return rows if isinstance(rows, list) else []


SIGNOFF_FIELDS = ("check_id", "subject", "fingerprint", "signer", "role", "reason", "date")


def _valid_signoff(row, check_id, subject, fingerprint):
    if not isinstance(row, dict) or any(not str(row.get(k) or "").strip() for k in SIGNOFF_FIELDS):
        return False
    gate = control.checks()[check_id]["gate"]
    role = control.load("gates")["gates"][gate]["signer"]
    return (row["check_id"] == check_id and row["subject"] == subject and row["fingerprint"] == fingerprint
            and row["role"] == role)


def add_signoff(path, check_id, subject, fingerprint, signer, role, reason, date=None):
    """Record a sign-off for one FLAG finding (fingerprint from the gate report), in the gate's signer role."""
    if check_id not in control.checks():
        raise ValueError(f"{check_id} is not a registered check")
    gate = control.checks()[check_id]["gate"]
    need = control.load("gates")["gates"][gate]["signer"]
    if role != need:
        raise ValueError(f"{check_id} is signed by the {need}, not '{role}'")
    if not str(signer).strip() or not str(reason).strip() or not str(fingerprint).strip():
        raise ValueError("a sign-off needs a signer, a reason and the finding's fingerprint")
    rows = load_signoffs(path)
    rows.append({"check_id": check_id, "subject": subject, "fingerprint": fingerprint, "signer": signer,
                 "role": role, "reason": reason, "date": date or _dt.date.today().isoformat()})
    Path(path).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return rows


@dataclass
class GateRun:
    gate: str
    subject: str
    results: list
    outcome: str
    allow_incomplete: bool
    ignored_signoffs: int = 0

    def counts(self):
        out = {}
        for r in self.results:
            out[r.status] = out.get(r.status, 0) + 1
        return out


def run_gate(gate, ctx, subject, signoffs=None, allow_incomplete=False):
    """Run every registered check of a gate on one subject."""
    _load_impl()
    so = signoffs or []
    results = []
    used = set()
    for cid, meta in control.checks().items():
        if meta["gate"] != gate:
            continue
        fn = REGISTRY.get(cid)
        if fn is None:
            results.append(Result(cid, "NOT_BUILT", f"built in phase {meta['phase']}", subject=subject))
            continue
        try:
            r = fn(ctx)
        except Exception as e:  # a crashing check is a Stop, never a silent pass; no exception text (may hold data)
            r = Result(cid, "STOP", f"check could not run ({type(e).__name__}); detail withheld because error "
                                    f"messages can contain raw file content")
        if not isinstance(r, Result) or r.status not in STATUSES:
            r = Result(cid, "STOP", "check returned an unknown status; treated as a Stop")
        r.check_id = cid
        r.subject = subject
        if r.status == "FLAG":
            fp = r.fingerprint()
            hit = [i for i, s in enumerate(so) if _valid_signoff(s, cid, subject, fp)]
            if hit:
                r.signed = so[hit[-1]]
                used.update(hit)
        results.append(r)
    st = [r.status for r in results]
    incomplete = "NOT_BUILT" in st
    if "STOP" in st:
        outcome = "STOP"
    elif incomplete and not allow_incomplete:
        outcome = "INCOMPLETE"
    elif any(r.status == "FLAG" and not r.signed for r in results):
        outcome = "FLAG"
    else:
        outcome = "PASS"
    if incomplete and allow_incomplete and outcome in ("PASS", "FLAG"):
        outcome += " (incomplete)"
    mine = [i for i, s in enumerate(so) if isinstance(s, dict) and s.get("subject") == subject
            and str(s.get("check_id", "")).startswith(gate + ".")]
    return GateRun(gate, subject, results, outcome, allow_incomplete,
                   ignored_signoffs=len([i for i in mine if i not in used]))


def _rows(run):
    meta = control.checks()
    gmeta = control.load("gates")["gates"][run.gate]
    out = []
    for r in run.results:
        m = meta[r.check_id]
        st = r.status + (" (signed)" if r.signed else "")
        out.append({"Check": r.check_id, "Title": m["title"], "Status": st, "Finding": r.message,
                    "Value": "" if r.value is None else str(r.value),
                    "Threshold": "" if r.threshold is None else str(r.threshold),
                    "What it means": m["plain"], "What to do": ACTION[r.status],
                    "Signer": gmeta["signer"] if r.status == "FLAG" else "",
                    "Signed by": (r.signed or {}).get("signer", ""), "Sign-off reason": (r.signed or {}).get("reason", ""),
                    "Fingerprint": r.fingerprint() if r.status == "FLAG" else "", "Built in": m["phase"]})
    return out


def write_report(runs, out_dir, name="gate_report", created=_dt.datetime(2026, 1, 1)):
    """Gate report as .xlsx (Summary, Checks, Details) and .md. Returns the two paths.

    The workbook's creation date is fixed (created) so the same results give a byte-identical file."""
    import xlsxwriter
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    xl = out_dir / f"{name}.xlsx"
    md = out_dir / f"{name}.md"
    wb = xlsxwriter.Workbook(str(xl))
    wb.set_properties({"created": created, "author": "Merit AI", "title": name})
    bold = wb.add_format({"bold": True})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    fills = {"PASS": "#D9EAD3", "STOP": "#F4CCCC", "FLAG": "#FFF2CC", "INFO": "#DEEAF6", "AUTO": "#DEEAF6",
             "NOT_BUILT": "#EEEEEE", "INCOMPLETE": "#EEEEEE"}
    fmt = {k: wb.add_format({"bg_color": v, "text_wrap": True, "valign": "top"}) for k, v in fills.items()}
    ws = wb.add_worksheet("Summary")
    ws.write_row(0, 0, ["Gate", "Name", "Subject", "Outcome", "Checks", "Pass", "Stop", "Flag", "Info / Auto",
                        "Not built", "Ignored sign-offs", "Merit AI"], bold)
    gm = control.load("gates")["gates"]
    for i, run in enumerate(runs, 1):
        c = run.counts()
        ws.write_row(i, 0, [run.gate, gm[run.gate]["name"], run.subject])
        ws.write(i, 3, run.outcome, fmt.get(run.outcome.split(" ")[0]))
        ws.write_row(i, 4, [len(run.results), c.get("PASS", 0), c.get("STOP", 0), c.get("FLAG", 0),
                            c.get("INFO", 0) + c.get("AUTO", 0), c.get("NOT_BUILT", 0), run.ignored_signoffs,
                            VERSION])
    ws.set_column(0, 11, 14)
    ws2 = wb.add_worksheet("Checks")
    head = ["Subject"] + list(_rows(runs[0])[0].keys()) if runs and runs[0].results else ["Subject"]
    ws2.write_row(0, 0, head, bold)
    i = 1
    for run in runs:
        for row in _rows(run):
            ws2.write(i, 0, run.subject, wrap)
            for j, k in enumerate(head[1:], 1):
                f = fmt.get(row["Status"].split(" ")[0]) if k == "Status" else wrap
                ws2.write(i, j, row[k], f)
            i += 1
    ws2.set_column(0, 0, 14)
    ws2.set_column(1, 1, 7)
    ws2.set_column(2, 2, 30)
    ws2.set_column(3, 3, 12)
    ws2.set_column(4, 4, 50)
    ws2.set_column(5, 6, 14)
    ws2.set_column(7, 8, 50)
    ws2.set_column(9, 13, 16)
    ws3 = wb.add_worksheet("Details")
    ws3.write_row(0, 0, ["Subject", "Check", "Detail"], bold)
    i = 1
    for run in runs:
        for r in run.results:
            for d in r.details:
                ws3.write_row(i, 0, [run.subject, r.check_id, json.dumps(d, sort_keys=True)])
                i += 1
    ws3.set_column(0, 1, 14)
    ws3.set_column(2, 2, 100)
    wb.close()
    lines = [f"# Gate report", "", f"Merit AI {VERSION}", ""]
    for run in runs:
        lines += [f"## {run.gate} {gm[run.gate]['name']} — {run.subject}: **{run.outcome}**", "",
                  "| Check | Title | Status | Finding |", "| --- | --- | --- | --- |"]
        for row in _rows(run):
            lines.append(f"| {row['Check']} | {row['Title']} | {row['Status']} | {row['Finding'].replace('|', '/')} |")
        lines.append("")
    md.write_text("\n".join(lines), encoding="utf-8")
    return xl, md
