"""Pinned Merit output contract (structure only) and the schema check of a Merit run folder.

A Merit run folder is the run's 04_Outputs (v7: csv/ and parquet/ subfolders) or any folder holding the
contract tables directly. Main tables are <name>.parquet or <name>.csv; recon_*, exceptions*, run_manifest*
are always CSV.

Reading is strict: a CSV whose header or rows do not parse exactly raises ReadError with a fixed message that
never contains file content (DuckDB's own errors quote raw lines, which may hold identifiers).
"""
import csv
import hashlib
import json
from pathlib import Path

import duckdb

from . import ROOT

CONTRACT_DIR = ROOT / "contract"
MAIN_TABLES = ["dim_life", "fact_member_month", "fact_claims", "cf_selected", "ultimates"]
FAMILIES = {"recon": "recon_*.csv", "exceptions": "exceptions*.csv", "run_manifest": "run_manifest*.csv"}
# strict text forms of the contract types (the contract: dates yyyy-mm-dd, '.' decimal, no thousands separator)
TYPE_RX = {"int": r"^-?[0-9]+$",
           "double": r"^-?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]+)?$",
           "date": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}


class ContractError(Exception):
    """The pinned contract itself is not the file it claims to be."""


class ReadError(Exception):
    """A table could not be read exactly. The message never carries file content."""


def load_pin():
    pin = json.loads((CONTRACT_DIR / "PIN.json").read_text(encoding="utf-8"))
    raw = (CONTRACT_DIR / pin["file"]).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != pin["sha256"]:
        raise ContractError(f"pinned contract hash {digest[:12]}... does not match PIN.json {pin['sha256'][:12]}...")
    contract = json.loads(raw.decode("utf-8"))
    if contract.get("version") != pin["version"]:
        raise ContractError(f"contract file version {contract.get('version')} differs from PIN.json {pin['version']}")
    return pin, contract


def columns(contract, table):
    return [(c, t) for c, t in contract["tables"][table].get("columns", [])]


def find_table(run_dir, name):
    """Path of a main table in a run folder: parquet first, then csv, in v7 subfolders or flat."""
    run_dir = Path(run_dir)
    for cand in (run_dir / "parquet" / f"{name}.parquet", run_dir / "csv" / f"{name}.csv",
                 run_dir / f"{name}.parquet", run_dir / f"{name}.csv"):
        if cand.exists():
            return cand
    return None


def find_family(run_dir, family):
    run_dir = Path(run_dir)
    pat = FAMILIES[family]
    return sorted(run_dir.glob(f"csv/{pat}")) or sorted(run_dir.glob(pat))


def _csv_header(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        try:
            return next(csv.reader(f))
        except StopIteration:
            raise ReadError(f"{path.name}: empty file (no header)") from None
        except (csv.Error, UnicodeDecodeError):
            raise ReadError(f"{path.name}: header could not be read") from None


def materialise(con, path, name="t"):
    """Load a table once into an in-memory DuckDB table (CSV read strictly, every column as text).

    Returns its column names. Raises ReadError (content-free message) if the file does not parse exactly.
    """
    path = Path(path)
    p = str(path).replace("'", "''")
    try:
        if path.suffix == ".parquet":
            con.execute(f'CREATE OR REPLACE TEMP TABLE "{name}" AS SELECT * FROM read_parquet(\'{p}\')')
            return [r[0] for r in con.execute(f'DESCRIBE "{name}"').fetchall()]
        head = _csv_header(path)
        if len(set(head)) != len(head) or any(h == "" for h in head):
            raise ReadError(f"{path.name}: header has blank or repeated column names")
        cols = "{" + ", ".join("'%s': 'VARCHAR'" % h.replace("'", "''") for h in head) + "}"
        con.execute(f'CREATE OR REPLACE TEMP TABLE "{name}" AS SELECT * FROM read_csv(\'{p}\', header=true, '
                    f"delim=',', quote='\"', escape='\"', skip=0, columns={cols}, strict_mode=true, "
                    f"null_padding=false, auto_detect=false)")
    except ReadError:
        raise
    except Exception:
        raise ReadError(f"{path.name}: rows do not parse as the header describes (ragged row, stray quote or "
                        f"bad encoding); content not shown") from None
    got = [r[0] for r in con.execute(f'DESCRIBE "{name}"').fetchall()]
    if got != head:
        raise ReadError(f"{path.name}: columns read differ from the header")
    return got


def manifest_values(run_dir):
    """Every Key -> list of (file, Value) across run_manifest*.csv (conflicts stay visible)."""
    out = {}
    con = duckdb.connect()
    try:
        for p in find_family(run_dir, "run_manifest"):
            materialise(con, p)
            for k, v in con.execute('SELECT "Key", "Value" FROM "t"').fetchall():
                out.setdefault(k, []).append((p.name, v))
    finally:
        con.close()
    return out


def manifest(run_dir):
    """run_manifest*.csv merged into one dict (Key -> Value); use manifest_values() to see conflicts."""
    return {k: v[-1][1] for k, v in manifest_values(run_dir).items()}


def _type_issues(con, table, typed):
    issues = []
    if not typed:
        return issues
    exprs = []
    for col, typ in typed:
        q = col.replace('"', '""')
        v = f'CAST("{q}" AS VARCHAR)'
        bad = f"NOT regexp_full_match({v}, '{TYPE_RX[typ]}')"
        if typ == "date":
            bad += f" OR TRY_CAST({v} AS DATE) IS NULL"
        if typ == "double":
            bad += f" OR NOT isfinite(TRY_CAST({v} AS DOUBLE))"
        exprs.append(f"count_if({v} IS NOT NULL AND {v} <> '' AND ({bad}))")
    counts = con.execute(f'SELECT {", ".join(exprs)} FROM "t"').fetchone()
    for (col, typ), n in zip(typed, counts):
        if n:
            issues.append({"kind": "type_error", "table": table, "column": col, "count": int(n),
                           "example": f"expected {typ}"})
    return issues


def check_schema(run_dir, required=None):
    """Issues of a run folder against the pinned contract.

    kind = unreadable / missing_table / missing_column / type_error / extra_column / missing_family.
    required = main tables that must exist (default: all five; the pool needs claims as well as premium).
    Values and column names outside the contract are never copied into the issues (they may be identifiers):
    an extra column is reported by position only.
    """
    _, contract = load_pin()
    required = MAIN_TABLES if required is None else required
    issues = []
    con = duckdb.connect()
    try:
        for t in MAIN_TABLES:
            path = find_table(run_dir, t)
            if path is None:
                if t in required:
                    issues.append({"kind": "missing_table", "table": t, "column": "", "count": 1, "example": ""})
                continue
            try:
                have = materialise(con, path)
            except ReadError as e:
                issues.append({"kind": "unreadable", "table": t, "column": "", "count": 1, "example": str(e)})
                continue
            issues += _table_issues(con, contract, t, t, have)
        for fam in FAMILIES:
            files = find_family(run_dir, fam)
            if not files:
                issues.append({"kind": "missing_family", "table": FAMILIES[fam], "column": "", "count": 1,
                               "example": ""})
            for p in files:
                try:
                    have = materialise(con, p)
                except ReadError as e:
                    issues.append({"kind": "unreadable", "table": p.stem, "column": "", "count": 1,
                                   "example": str(e)})
                    continue
                if contract["tables"][fam].get("columns"):
                    issues += _table_issues(con, contract, fam, p.stem, have)
    finally:
        con.close()
    return issues


def _table_issues(con, contract, ctab, label, have):
    issues = []
    typed = []
    for col, typ in columns(contract, ctab):
        if col not in have:
            issues.append({"kind": "missing_column", "table": label, "column": col, "count": 1, "example": ""})
        elif typ in TYPE_RX:
            typed.append((col, typ))
    issues += _type_issues(con, label, typed)
    known = {c for c, _ in columns(contract, ctab)}
    for i, col in enumerate(have, 1):
        if col not in known:
            issues.append({"kind": "extra_column", "table": label, "column": f"(column {i})", "count": 1,
                           "example": ""})
    return issues
