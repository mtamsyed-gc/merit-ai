"""Pinned Merit contract: hash guard, and the schema check finds every kind of problem."""
import shutil
import tempfile
from pathlib import Path

import pandas as pd
from helpers import copy_run, done, ok, pack, tmpdir

from meritai import contract as K

pin, c = K.load_pin()
ok(pin["version"] == "IP4-13" and c["version"] == "IP4-13", "pinned contract IP4-13 (Merit v10.7.0) loads, hash verified")
ok(pin["source_commit"].startswith("52da4ce"), "pinned from ete-dashboard 52da4ce (Merit v10.7.0)")
ok(set(K.MAIN_TABLES) <= set(c["tables"]), "contract holds the five main tables")

# tampered contract is refused
tmp = tmpdir('t_')
shutil.copytree(K.CONTRACT_DIR, tmp / "contract")
f = tmp / "contract" / pin["file"]
f.write_text(f.read_text(encoding="utf-8").replace('"LifeID"', '"LifeIdent"', 1), encoding="utf-8")
orig = K.CONTRACT_DIR
K.CONTRACT_DIR = tmp / "contract"
try:
    K.load_pin()
    ok(False, "tampered contract refused")
except K.ContractError:
    ok(True, "tampered contract refused")
K.CONTRACT_DIR = orig

d, truth = pack()
for code in sorted(truth["cedants"]):
    iss = K.check_schema(d / code / "04_Outputs")
    ok(iss == [], f"synthetic {code} conforms to the contract")

run = copy_run(d)
p = run / "csv" / "dim_life.csv"
df = pd.read_csv(p, dtype=str, keep_default_na=False)
df.drop(columns=["Gender"]).assign(UWY=lambda x: x["UWY"].where(x.index > 2, "20X5")).to_csv(p, index=False)
(run / "csv" / "ultimates.csv").unlink()
(run / "csv" / "fact_claims.csv").rename(run / "csv" / "fact_claims.csv.bak")
kinds = {(i["kind"], i["table"], i["column"]) for i in K.check_schema(run)}
ok(("missing_column", "dim_life", "Gender") in kinds, "missing column found")
ok(any(k == ("type_error", "dim_life", "UWY") for k in kinds), "type error found (UWY not an integer)")
ok(("missing_table", "ultimates", "") in kinds, "missing table found")
ok(("missing_table", "fact_claims", "") in kinds, "missing claims table found")
ex = [i for i in K.check_schema(run) if i["kind"] == "type_error"]
ok(all("20X5" not in i["example"] for i in ex), "values are never copied into issues")

# exceptions family: each file carries its own amount columns (Merit IP4-12, TPA_RULES 93.6)
names = lambda stem: [c for c, _ in K.columns(c, "exceptions", stem)]  # noqa: E731
ok("Gross Premium" in names("exceptions") and "Payer Share" not in names("exceptions"),
   "exceptions.csv: premium amounts, no payer share")
ok("Payer Share" in names("exceptions_claims") and "Net Premium" not in names("exceptions_claims"),
   "exceptions_claims.csv: payer share, no premium amounts")
run3 = copy_run(d)
p3 = run3 / "csv" / "exceptions_claims.csv"
pd.read_csv(p3, dtype=str, keep_default_na=False).assign(**{"Gross Premium": ""}).to_csv(p3, index=False)
k3 = {(i["kind"], i["table"]) for i in K.check_schema(run3)}
ok(k3 == {("extra_column", "exceptions_claims")}, "a premium amount in exceptions_claims.csv is outside the contract")

# parquet is read first when both exist
run2 = copy_run(d)
(run2 / "parquet").mkdir()
pd.read_csv(run2 / "csv" / "cf_selected.csv").to_parquet(run2 / "parquet" / "cf_selected.parquet", index=False)
ok(K.find_table(run2, "cf_selected").suffix == ".parquet", "parquet preferred over csv")
ok(K.check_schema(run2) == [], "parquet table passes the schema check")
done("test_contract")
