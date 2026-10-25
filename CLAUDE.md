# Merit AI — standing instructions for Claude

Read HANDOVER.md first: it says where the build is and what is blocked.

## What this repository is
Merit AI builds pooled UAE medical benchmarks and predictive models from the outputs of Merit
(repo mtamsyed-gc/ete-dashboard, folder side_tools/merit). It READS Merit's output contract and never
changes Merit. A change Merit needs (for example stamping its contract version) is raised as a Merit
change request in that repository, never patched from here.

## Source of truth
- SPEC.md = export of the Claude Doc "UAE Medical Predictive Analytics — Implementation Path"
  (https://claude.ai/artifact/CXpt27kyqoqk3K3cqjFDgj). The doc is the master; re-export SPEC.md after any change.
- Background: "UAE Medical Portfolio Predictive Analytics — Project Brief" (https://claude.ai/artifact/E7LLAKRdSzRxNtkRJ9yC1v).
- Decisions D-1 .. D-10 (SPEC "Decisions needed") are binding; a DECIDED row overrides any *proposed* value
  earlier in SPEC. If SPEC is silent or ambiguous, stop and ask the owner. Never invent business logic.
- Thresholds, maps and classes live in control/*.json (versioned). Code reads them; code never hard-codes a threshold.

## Runtime
- Native CPython 3.12+ on Windows (owner laptop runs 3.14), packages pinned in requirements.txt, installed
  per user from GC Artifactory. Allowed imports: stdlib + requirements.txt. Anything else needs owner approval and a pin.
- Code runs on pandas 3.x (copy-on-write, string dtype) and numpy 2.x.
- Launchers are numbered .cmd files in launchers/ calling `py run.py <command>`. Never .ps1. Paths resolved
  from run.py's own location, never from the current directory. No network calls, no GUI.
- Storage: Parquet + DuckDB in folders that are never committed (pool/, runs/, out/).

## Engineering rules
- Every gate check is registered in control/gates.json (id, gate, level, threshold key, phase, plain text).
  A check is either built (a function in meritai/checks/) or pending. Every built check has a fail-on-purpose
  case in tests/test_gate_cases.py; the registry test fails if one is missing.
- Gate outcome: any Stop -> STOP; any Flag without a sign-off -> FLAG; else PASS. Info never blocks.
  Overrides are signed Flags in the sign-off register, never a bypass.
- Deterministic: same inputs + versions = byte-identical outputs. Random steps take a recorded seed.
- Each model is proven on synthetic data with planted effects (synth/truth.json) before it touches the pool.
- Plain-language text for every check and output lives in control files, not scattered in code.

## Data boundary (non-negotiable)
- This repository holds code, control files and synthetic data only. Never commit pool data, Merit run outputs
  from real cedants, member or policy identifiers, cedant names or the pool-ID key file.
- Synthetic cedants carry fictitious names. TPA and network NAMES appear in control/crosswalk.json as
  configuration (owner's tier map, D-1); never values from real files.
- Real pool data lives only on the GC laptop (D-9); the build laptop holds synthetic data only.

## Working method
- One phase (P1 .. P7, SPEC "Build sequence") per session. Start by restating its acceptance criteria and plan.
- Tests: plain Python, `py tests/run_all.py`. All pass before every commit.
- End of every session: update HANDOVER.md (status, next step), commit "P<n>: <summary>", push.
