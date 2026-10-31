"""Pinned Merit contract: hash guard, and the schema check finds every kind of problem."""
import shutil
import tempfile
from pathlib import Path

import pandas as pd
from helpers import copy_run, done, ok, pack, tmpdir

from meritai import contract as K

pin, c = K.load_pin()
ok(pin["version"] == "IP4-11" and c["version"] == "IP4-11", "pinned contract IP4-11 (Merit v7.8.2) loads, hash verified")
ok(pin["source_commit"].startswith("0fa7e5b"), "pinned from ete-dashboard 0fa7e5b (Merit v7.8.2)")
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

# parquet is read first when both exist
run2 = copy_run(d)
(run2 / "parquet").mkdir()
pd.read_csv(run2 / "csv" / "cf_selected.csv").to_parquet(run2 / "parquet" / "cf_selected.parquet", index=False)
ok(K.find_table(run2, "cf_selected").suffix == ".parquet", "parquet preferred over csv")
ok(K.check_schema(run2) == [], "parquet table passes the schema check")
done("test_contract")
