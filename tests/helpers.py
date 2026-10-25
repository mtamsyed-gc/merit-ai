"""Shared test helpers (plain Python; no test framework)."""
import atexit
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from meritai import synth  # noqa: E402

FAILS = []
_TMP = []


def tmpdir(prefix):
    d = Path(tempfile.mkdtemp(prefix=prefix))
    _TMP.append(d)
    return d


@atexit.register
def _cleanup():
    for d in _TMP:
        shutil.rmtree(d, ignore_errors=True)


def ok(cond, msg):
    if cond:
        print(f"  ok   {msg}")
    else:
        print(f"  FAIL {msg}")
        FAILS.append(msg)


def done(name):
    if FAILS:
        print(f"{name}: {len(FAILS)} failure(s)")
        sys.exit(1)
    print(f"{name}: all passed")


@lru_cache(maxsize=None)
def pack(scale=0.03, seed=None, stamp=False):
    """A synthetic pack in a temporary folder (cached per process)."""
    d = tmpdir("meritai_pack_")
    truth = synth.generate(d, seed=seed, scale=scale, stamp_contract=stamp, progress=lambda m: None)
    return d, truth


def copy_run(pack_dir, code="C01"):
    """A writable copy of one cedant's Merit run folder (04_Outputs)."""
    d = tmpdir("meritai_run_")
    shutil.copytree(Path(pack_dir) / code / "04_Outputs", d / "04_Outputs")
    return d / "04_Outputs"
