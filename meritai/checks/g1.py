"""Gate G1 (Ingest) checks built in P1: G1.1 contract, G1.4 identifiers. The rest of G1 is built in P2.

ctx keys:
  run_dir          a Merit run folder (04_Outputs) or an anonymised submission folder
  allowed_columns  optional {table: [columns]} for G1.4 (the submission export's allow-list, P2)

No result ever carries a data value or an unknown column name: only table names, contract column names,
positions and counts.
"""
import duckdb

from .. import contract as K
from .. import control
from ..gates import Result, check, fail_level


@check("G1.1")
def g1_1(ctx):
    th = control.threshold("G1.1")
    pin, _ = K.load_pin()
    issues = K.check_schema(ctx["run_dir"])
    hard = [i for i in issues if i["kind"] != "extra_column"]
    extra = [i for i in issues if i["kind"] == "extra_column"]
    details = [dict(i) for i in hard + extra]
    if hard:
        kinds = sorted({i["kind"].replace("_", " ") for i in hard})
        return Result("G1.1", fail_level("G1.1"), f"{len(hard)} contract problem(s): {', '.join(kinds)}",
                      value=len(hard), threshold=0, details=details)
    stamps = K.manifest_values(ctx["run_dir"]).get("contract_version", [])
    values = sorted({v for _, v in stamps})
    note = (f"{len(extra)} extra column(s) not in the contract (ignored)" if extra
            else "all contract tables and columns present")
    if len(values) > 1:
        return Result("G1.1", fail_level("G1.1"), f"the run's manifests carry conflicting contract versions "
                                                  f"({', '.join(values)})", value=values, threshold=pin["version"],
                      details=details + [{"file": f, "contract_version": v} for f, v in stamps])
    if values and values[0] != pin["version"]:
        return Result("G1.1", fail_level("G1.1"), f"run stamped contract {values[0]}; this release accepts "
                                                  f"{pin['version']}", value=values[0], threshold=pin["version"],
                      details=details)
    if not values:
        lvl = th["contract_version_missing_level"].upper()
        return Result("G1.1", lvl, f"schema matches contract {pin['version']}; {note}; the run carries no "
                                   f"contract_version stamp (Merit does not write one yet)",
                      value="not stamped", threshold=pin["version"], details=details)
    return Result("G1.1", "PASS", f"contract {pin['version']}; {note}", value=values[0], threshold=pin["version"],
                  details=details)


def _tables(run):
    out = [(t, K.find_table(run, t)) for t in K.MAIN_TABLES]
    for fam in K.FAMILIES:
        out += [(p.stem, p) for p in K.find_family(run, fam)]
    return [(t, p) for t, p in out if p is not None]


def _known_columns(contract, table):
    key = table if table in K.MAIN_TABLES else next((f for f in K.FAMILIES if table.startswith(f)), None)
    return {c for c, _ in K.columns(contract, key)} if key else set()


@check("G1.4")
def g1_4(ctx):
    th = control.threshold("G1.4")
    pats = sorted(th["patterns"].items())
    _, contract = K.load_pin()
    con = duckdb.connect()
    hits, extra_cols, unread = [], [], []
    allowed = ctx.get("allowed_columns")
    try:
        for t, path in _tables(ctx["run_dir"]):
            try:
                have = K.materialise(con, path)
            except K.ReadError as e:
                unread.append({"table": t, "kind": "unreadable", "reason": str(e)})
                continue
            known = _known_columns(contract, t)
            label = lambda i, c: c if c in known else f"(column {i})"  # noqa: E731
            if allowed is not None:
                ok = set(allowed.get(t, []))
                extra_cols += [{"table": t, "column": label(i, c), "kind": "column not allowed"}
                               for i, c in enumerate(have, 1) if c not in ok]
            for i, c in enumerate(have, 1):            # a column name can itself be an identifier
                for name, rx in pats:
                    if con.execute("SELECT regexp_matches(?, ?)", [c, rx]).fetchone()[0]:
                        hits.append({"table": t, "column": f"(column {i}) header", "pattern": name, "rows": 1})
            pairs = [(i, c, name, rx) for i, c in enumerate(have, 1) for name, rx in pats]
            if not pairs:
                continue
            exprs = ["count_if(regexp_matches(CAST(\"%s\" AS VARCHAR), '%s'))"
                     % (c.replace('"', '""'), rx.replace("'", "''")) for _, c, _, rx in pairs]
            counts = con.execute(f'SELECT {", ".join(exprs)} FROM "t"').fetchone()
            for (i, c, name, _), n in zip(pairs, counts):
                if n:
                    hits.append({"table": t, "column": label(i, c), "pattern": name, "rows": int(n)})
    finally:
        con.close()
    if unread:
        return Result("G1.4", fail_level("G1.4"), f"{len(unread)} table(s) could not be read exactly, so they "
                                                  f"cannot be cleared of identifiers", value=len(unread),
                      threshold=0, details=unread)
    found = sum(h["rows"] for h in hits)
    if found > th["max_hits"] or extra_cols:
        parts = []
        if found:
            parts.append(f"{found} value(s) look like identifiers "
                         f"({', '.join(sorted({h['pattern'] for h in hits}))})")
        if extra_cols:
            parts.append(f"{len(extra_cols)} column(s) outside the allowed list")
        return Result("G1.4", fail_level("G1.4"), "; ".join(parts) + ". Values are not shown in this report.",
                      value=found + len(extra_cols), threshold=th["max_hits"], details=hits + extra_cols)
    scope = ("names are covered by the allowed-column list" if allowed is not None
             else "names are not pattern-detectable and are covered by the allowed-column list from P2")
    return Result("G1.4", "PASS", f"no ID, e-mail or phone patterns in any header or value; {scope}", value=0,
                  threshold=th["max_hits"])
