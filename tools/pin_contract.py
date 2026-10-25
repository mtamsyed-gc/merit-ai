"""Pin Merit's output contract: keep only the structure (tables, columns, types, keys), drop the descriptions.

Merit's contract file carries free-text descriptions that mention real cedants and reinsurers; Merit AI commits
no cedant names, so it pins a structure-only copy and records the hash of the source file it came from.

  py tools/pin_contract.py <path to ete-dashboard>/side_tools/merit/config/model_contract.json <source commit>
"""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "contract"
KEEP = ("columns", "key", "grain", "optional", "files")


def strip(src):
    out = {"version": src["version"], "tables": {}}
    for t, v in src["tables"].items():
        out["tables"][t] = {k: v[k] for k in KEEP if k in v}
    return out


def main(path, commit):
    raw = Path(path).read_bytes()
    src = json.loads(raw.decode("utf-8"))
    pinned = strip(src)
    text = json.dumps(pinned, indent=1, sort_keys=True) + "\n"
    (OUT / "merit_model_contract.json").write_text(text, encoding="utf-8", newline="\n")
    pin = {"_note": "Structure-only copy of Merit's output contract (descriptions dropped: they name real cedants). "
                    "Merit AI accepts only this version. A Merit release that changes the contract needs a change "
                    "request here: re-run tools/pin_contract.py, re-run the tests.",
           "source_repo": "mtamsyed-gc/ete-dashboard", "source_path": "side_tools/merit/config/model_contract.json",
           "source_commit": commit, "source_sha256": hashlib.sha256(raw).hexdigest(),
           "pinned_on": dt.date.today().isoformat(), "version": src["version"],
           "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "file": "merit_model_contract.json"}
    (OUT / "PIN.json").write_text(json.dumps(pin, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"pinned {src['version']} from {commit}: {pin['sha256'][:12]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
