# Handover — Merit AI

Last updated: 2026-10-25 (P1 Foundations; contract re-pinned to Merit v7.3.2 source a350841, synthetic runs stamped).

Read this, then CLAUDE.md, then the SPEC.md sections the task names.

## What this is
Pooled UAE medical benchmarks and predictive models built on Merit's output contract (Merit = repo
mtamsyed-gc/ete-dashboard, side_tools/merit). Merit is read, never changed.

## Master documents
| Document | Link | Copy here |
| --- | --- | --- |
| Implementation Path (master spec: streams, gates G1-G7, phases P1-P7, decisions D-1..D-10) | https://claude.ai/artifact/CXpt27kyqoqk3K3cqjFDgj (doc id 5d625861-814f-4631-83c6-fb3fb75a0940) | SPEC.md (exported 2026-10-25, rev 44: phases added in text so the export carries them) |
| Project Brief | https://claude.ai/artifact/E7LLAKRdSzRxNtkRJ9yC1v | — |

If the doc and SPEC.md disagree, the doc wins; re-export after any change.

## Decisions in force (all taken 2026-10-25; detail in SPEC "Decisions needed")
D-1 pool vocabulary: 7 network tiers by rate-table position (CN, GN, GN excl. Mediclinic filed on GN, RN, RN2, RN3,
VN) across NAS / NextCare / Mednet / AAFIYA / E-Care, roll-up Top / Mid / Basic; 3 regulator regions; six benefit
groups; government schemes excluded. D-2 match rate banded 95 / 85 on in-scope claims. D-3 credibility 90% / 10%
on capped CV, client K at policyholder level, badges 0.7 / 0.3, M2 needs 5 cedants. D-4 two-tier disclosure.
D-5 trend benchmark only until M1. D-6 PNLR link only after M3 (Merit change request). D-7 large claims per
claimant-year, provisional AED 500k. D-8 statsmodels + scipy (Artifactory confirmed), R offline as reference.
D-9 build on the owner's laptop with synthetic data, pool on a GC laptop; owner = pool and model owner; SB = key
custodian and model-fitting deputy; G5 reviewer = GC actuary outside the build. D-10 quarterly window with a
materiality test; annual recalibration finished by April.

## Status
| Phase | State |
| --- | --- |
| P1 Foundations | Built 2026-10-25 — see "P1" below |
| P2 Pool v1 (Streams 1-2) | Not started |
| P3-P7 | Not started |

## P1 (2026-10-25)
Acceptance (SPEC, P1 row): every gate check fails on purpose in tests; launchers run end to end on synthetic data.
Interpreted for P1 as: all 48 checks registered with level, threshold and plain text; the checks P1 builds (G1.1
contract, G1.4 identifiers) each have fail-on-purpose cases, and a registry test makes every later-built check add
its own; `launchers\00_Self_test.cmd` runs control -> contract -> synthetic pool -> G1 -> gate report.

Built:
- `control/`: gates.json GR-1.0 (48 checks = SPEC tables, tested against SPEC.md incl. levels and phases),
  thresholds.json TH-1.0 (D-2..D-10 values), crosswalk.json CW-1.1 (D-1 tier map exactly as the owner's table,
  roll-up, regulators; benefit-group map proposed), disclosure.json DS-1.1 (D-4; four measure placements proposed).
- `contract/`: Merit contract IP4-8 pinned STRUCTURE-ONLY (descriptions dropped: they name real cedants) by
  `tools/pin_contract.py`; re-pinned 2026-10-25 from ete-dashboard a350841 (Merit v7.3.2, manifest key contract_version
  documented; pinned copy unchanged, 1c71f611...). Synthetic runs now carry contract_version as v7.3.2 runs do
  (`run.py synth --no-stamp` writes pre-v7.3.2 manifests).
- Strict reading (`meritai/contract.py`): CSV header and rows must parse exactly (no sniffing); any parse failure is
  a Stop with a content-free message; strict type forms (int, yyyy-mm-dd, finite decimal).
- `meritai/synth.py` + `synth/plant.json` PL-1.0: six fictitious cedants as Merit v7 run folders; planted
  frequency / severity relativities (age, gender, tier, regulator, policy type), trend 2% / 6%, seasonality,
  cedant and policyholder effects (recorded per master contract in truth.json), Pareto large losses, TPA reporting
  patterns, match rates (one cedant 91% = restricted band, one 82% = reject band); premium priced on the rate manual
  only, so loss ratios carry the hidden group effects for M3; raw networks in mixed case; byte-identical per seed.
- `meritai/gates.py`: STOP > INCOMPLETE > FLAG > PASS (dev runs labelled "(incomplete)"); unknown statuses and
  crashes are Stops with no exception text; sign-offs bind check + subject + finding fingerprint + signer role.
- Checks G1.1 (structure vs pinned contract, family files, conflicting / wrong version stamps) and G1.4 (every
  header and value of every table, incl. numeric columns, recon, manifests, parquet; no false positives on keyed
  hashes or decimals).
- `run.py` CLI (selftest, synth, contract, gate, signoff) with a package check; launchers 00/01 (pushd, CRLF);
  README in plain language.
- Tests: 6 suites, all pass (`python3 tests/run_all.py`, about 2 min): 16 G1.1 and 19 G1.4 fail-on-purpose cases,
  each also proving no value reaches the report; generator checked independently of its own bookkeeping
  (claim counts by tier / regulator / age / year within Poisson noise, severity incl. trend, Pareto alpha,
  policyholder spread). Ran on exactly the pinned package versions (Python 3.13 in the build container).
- Independent review (2026-10-25): 1 blocker (crash text leaking raw rows) and 10 majors found; all fixed or
  raised as owner questions below.

Open questions for the owner (defaults in use):
| # | Question | In use |
| --- | --- | --- |
| Q1 | DONE in Merit v7.3.2 (2026-10-25, ete-dashboard a350841): both run manifests carry `contract_version`. Open part: a run from Merit v7.3.1 or earlier (no stamp): re-run on v7.3.2 before pooling (recommended; G1.1 missing-stamp level -> Stop, as SPEC) or accept with a signed Flag? | Missing stamp = FLAG until the owner answers |
| Q2 | Merit's FOB list has no Pharmacy class. Proposed: Out-Patient lines at a Pharmacy provider = Pharmacy; a TPA with no pharmacy provider type = "OP incl. pharmacy". Also confirm the six group codes and the FOB -> group map | Proposed |
| Q3 | Merit FOB values outside the six groups (Psychiatry, Alternative Medicine, Wellness & Preventive, Assistance, Other): which group, if any? | Unmapped (G2.3 counts them) |
| Q4 | Government-funded schemes are excluded (D-1): which Merit field identifies them? | Open |
| Q5 | Mandatory-basic segment (EBP / Basic): which field or network marks it beyond AAFIYA APN (Enhanced EBP)? | Proposed |
| Q6 | P1 acceptance says "every gate check fails on purpose". Built in P1: G1.1 and G1.4 (each with its cases); the other 46 are registered and must each add cases when their phase builds them (enforced by test). Accept this reading? | As stated |
| Q7 | AAFIYA "APN Edge / Essential": one network or two names? | Only the literal name maps |
| Q8 | G1.2 tolerance for the member-month fan-out: 0.01 (Merit manual 3.13 "0 within rounding, < 0.01")? | 0.01 |
| Q9 | Disclosure class for trend rates, completion factors and provider / diagnosis indices: loss-cost (3 / 50% / 500 LY)? | Loss-cost (proposed) |
| Q10 | Merit change request bundle | (a) done in v7.3.2; nothing else open |

## Next step
1. Done 2026-10-25 18:05: repository mtamsyed-gc/merit-ai created; main = e1c9429 (P1).
2. Owner: run `launchers\00_Self_test.cmd` and `01_Run_tests.cmd` on the laptop after installing requirements.txt.
3. Owner: answer Q1-Q6.
4. P2 Pool v1: Stream 1 submission export + anonymisation (pool IDs, keyed hashes, allow-list) and Stream 2
   comparability, with G1.2, G1.3, G1.5-G1.8 and G2.1-G2.7 built and fail-on-purpose tested.
