"""Merit AI: pooled UAE medical benchmarks and predictive models built on Merit's output contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
