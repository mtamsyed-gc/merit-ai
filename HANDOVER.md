# Handover — Merit AI

Last updated: 2026-11-16 (packages aligned with Merit v10: Python 3.14, duckdb 2.0.0, no fetchone(); owner answered Q1, Q8 and Q13(b); thresholds TH-1.1. Before: 2026-11-15 (contract re-pinned to IP4-13 = Merit v8.0.9 onwards, current Merit v10.7.0, ete-dashboard 52da4ce, owner: "If MeritAI needs contract pinning do that"; synthetic runs carry the IP4-12 / IP4-13 columns; the exceptions files are checked per file. Before: 2026-10-31 (contract re-pinned to IP4-11 = Merit v7.8.2, ete-dashboard 0fa7e5b, owner's instruction; synthetic runs carry the IP4-10 scope columns. Before: 2026-10-26 (contract re-pinned to IP4-9 = Merit v7.5.0, ete-dashboard 3eaaa30, owner's instruction; before: 2026-10-25 P1 Foundations, re-pin to the Merit v7.3.2 source a350841, synthetic runs stamped).

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
  thresholds.json TH-1.1 (D-2..D-10 values; 2026-11-16: Q1 and Q8 decided), crosswalk.json CW-1.1 (D-1 tier map exactly as the owner's table,
  roll-up, regulators; benefit-group map proposed), disclosure.json DS-1.1 (D-4; four measure placements proposed).
- `contract/`: Merit contract pinned STRUCTURE-ONLY (descriptions dropped: they name real cedants) by
  `tools/pin_contract.py`. **Re-pinned 2026-11-15 to IP4-13** from ete-dashboard 52da4ce (Merit v10.7.0; source sha256 50ac4cff...; pinned 3c570f28...). See "Merit IP4-13" below. Before: **re-pinned 2026-10-31 to IP4-11** (owner: "Pin latest IP4 to Merit AI and Pricing Workbench") from ete-dashboard 0fa7e5b (Merit v7.8.2; source sha256 ee20699e...; pinned ea876ad4...). See "Merit IP4-11" below. Before: **re-pinned 2026-10-26 to IP4-9** (owner 14:54: "Re-Pin Pricing Workbench and Merit
  AI") from ete-dashboard 3eaaa30 (Merit v7.5.0; source sha256 6ba0c198...; pinned 7ba05426...). Tables, columns,
  types and keys are unchanged: only the version moves. See "Merit IP4-9" below. Before: IP4-8, re-pinned 2026-10-25 from ete-dashboard a350841 (Merit v7.3.2, manifest key contract_version
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

Packages aligned with Merit (2026-11-16, owner: "Align packages with Merit"): requirements.txt duckdb 1.5.6 -> 2.0.0
and the runtime is CPython 3.14, as Merit v10.0.0 onwards (ete-dashboard requirements-native.txt); every package the
two share carries Merit's version. The three fetchone() calls became `contract.one_row` (DuckDB 2.0 keeps a result
open after fetchone(); Merit's rule). No `~`, single-arrow lambda or explicit transaction in the SQL. Tests: 6 suites
pass on Python 3.14.6 with duckdb 2.0.0 in the cloud. Owner: re-install requirements.txt on the laptop before the
self-test (duckdb moved).

Merit IP4-13 (Merit v8.0.9 onwards; current Merit v10.7.0; ete-dashboard side_tools/merit TPA_RULES 93 and 98). Both
steps since IP4-11 are additive: no table or column is removed or renamed.
- **IP4-12 (Merit v8.0.4), optional fields and exception amounts:** dim_life and dim_life_excluded carry Opt_1..Opt_5
  (text, raw values a cedant maps case by case; blank when not mapped). exceptions.csv carries Gross Premium and Net
  Premium; exceptions_claims.csv carries Payer Share. The contract lists all three under one "exceptions" entry, so
  `meritai/contract.py` FILE_COLUMNS says which file carries which (a missing one is a Stop; one in the other file is
  an extra column, ignored by G1.1 as any extra column is).
- **IP4-13 (Merit v8.0.9), reinsured shares:** dim_life and dim_life_excluded carry ReinsuredPct, ReinsuredPctSource,
  TreatyCededPct and CededPct.
- **G1.1:** a run stamped IP4-11 or IP4-12 (Merit v7.7.0 to v8.0.8) is now refused ("this release accepts IP4-13";
  fail level Stop). Re-run it on Merit v8.0.9 or later before pooling (Q13).
- **G1.4:** Opt_1..Opt_5 are free text from the cedant's files, so they can hold identifiers or names. G1.4 scans
  them like every column (fail-on-purpose case added); names are not pattern-detectable, so the P2 allowed-column
  list has to decide whether they enter the pool at all (Q13).
- **Synthetic runs:** stamped IP4-13; Opt_1..Opt_5 blank; ReinsuredPct 1 with source "Payer not in the policy table:
  100%", TreatyCededPct and CededPct blank (what Merit writes with no RI tabs); exception amounts blank.
- Tests: 6 suites pass (22 G1.1 and 20 G1.4 fail-on-purpose cases) on the pinned packages, Python 3.13.

Merit IP4-11 (Merit v7.7.0 onwards; current Merit v7.8.2; ete-dashboard side_tools/merit/docs/RELEASE_NOTES_v7.6.0.md
and RELEASE_NOTES_v7.7.0.md). Both steps since IP4-9 are additive: no table or column is removed or renamed.
- **IP4-10 (Merit v7.6.0), scope register:** new columns ScopeStatus and ScopeRule on dim_life, fact_member_month and
  fact_claims; PayerShareCapped and PayerShareExcess on fact_claims; new optional tables dim_life_excluded,
  fact_member_month_excluded, fact_claims_excluded (rows an EXCLUDE rule removed), scope_tags, diagnostics,
  dq_recon_scope, dq_recon_control, dq_quarantine. The main tables now hold in-scope rows only; a CARVEOUT has already
  reduced premium and removed the benefit's claims; a CAP leaves Paid / OS as reported and writes the capped share
  beside it. Pooling reads the main tables, so excluded business stays out of the pool (Q12).
- **IP4-11 (Merit v7.7.0), development factors:** cf_selected carries Source, CF_Derived, Credible, Cohorts, Claims
  (data-derived factors from the new 03b workflow); run_manifest_claims carries development_factors and development_bf.
- **G1.1:** a run stamped IP4-9 or IP4-10 (Merit v7.5.0 to v7.6.x) is now refused ("this release accepts IP4-11";
  fail level Stop). Re-run it on Merit v7.7.0 or later before pooling (Q12).
- **Synthetic runs:** stamped IP4-11; every main-table row In scope, no scope rule, PayerShareCapped = PayerShare
  and PayerShareExcess = 0 (what Merit writes when the scope register is empty). Optional twin and diagnostics tables
  are not generated.

Merit IP4-9 (Merit v7.5.0, owner decisions on the Merit Phase 1 Q-list; ete-dashboard
side_tools/merit/docs/RELEASE_NOTES_v7.5.0.md): the meanings change and the layout does not. Effect here:
- **G1.1:** a run stamped IP4-8 (Merit v7.4.0 or earlier) is now refused ("this release accepts IP4-9"; fail level
  Stop). Re-run it on Merit v7.5.0 before pooling (Q11).
- **CountFlag:** now on a visit's first paid line when the visit's net paid is above zero. Counts per cell do not
  change. A count cut by a line attribute (provider or claim type) can.
- **PolicyTypeUsed:** where Merit calculates the type, it is now "SME" or "Group" (one rule: lives in force at
  inception below SME max lives, default 200). It was "SME" / "Non-SME". Supplied policy types pass through as before.
- **UltimateAmount / ultimates:** for a TPA with an expected loss ratio in Merit's Run settings, the lag-0 month is
  Bornhuetter-Ferguson (Method starts "BF:"). Those months have completion factors around 0.4-0.6, below the
  0.80 maturity threshold, so SPEC's maturity control already keeps them out of calibration. In monitoring they
  carry an assumed loss ratio, not a development estimate (Q11).
- **Synthetic runs:** stamped IP4-9 (the generator writes the pinned version).

SPEC re-read against Merit v10.7.0 (2026-11-16, owner's instruction; SPEC.md is the 2026-10-25 export, written at
Merit v7.3). Findings to settle before the phase named; none is applied to SPEC or code yet (the doc is the master).
| # | Phase | Finding | Proposed |
| --- | --- | --- | --- |
| R1 | P2 | G1.2 ("no Stop exception codes") contradicts G1.3 / D-2: Merit writes E-CL-MATCHRATE with Severity Stop below 95% match (config/message_codes.csv) and the run continues, so a run in D-2's 85-95% restricted band always carries a Stop code | G1.2 ignores E-CL-MATCHRATE; G1.3 governs the match rate |
| R2 | P2 | D-2's match rate (less pre-inception, out-of-cover, reversals) is not Merit's: recon_claims counts out-of-cover lines as matched and has no reversals column | Owner states D-2 as a formula on recon_claims columns, or a Merit change request |
| R3 | P2 | Stream 1 tags "Merit version" and "data tier T0-T3 (SPEC section 5)": the manifests carry workflow_version and contract_version, no pack version, engine or tier; SPEC section 5 belongs to the retired ETE spec | Tag the workflow versions; owner defines the tiers here |
| R4 | P2 | Not in SPEC: scope register (main tables in scope only; *_excluded twins; RESHARE / CARVEOUT / CAP rows), currency (manifest stamped AED for SAR / QAR payers before Merit v8.0.12), secondary member identifier (MemKey can be a salted hash that changes when a client folder is rebuilt) | G1 Stop when dim_life Currency is not AED or Country not UAE; Q12 (b) for scope; owner rule for the member token |
| R5 | P2 | Maturity control assumes chain-ladder ultimates: since v7.7.0 the youngest months can be Bornhuetter-Ferguson / Benktander (ultimates.Method), an assumed loss ratio and not experience | Leave those months out of calibration as well as CF below 0.80 |
| R6 | P3 | Development benchmark: Merit's 03b factors use 90% / 5% credibility, D-3 is 90% / 10%; cf_selected Source says which factors are data-derived; the dev_* triangles are not in the contract | Pool only derived factors; record the two standards as deliberate |
| R7 | P4 | D-5 and M1 point to "SPEC D22 10%" and "P5b" of the retired engine; Merit's live trend inputs are PNLR 8% and the development workbook's prior trend. G5's baseline "Merit's one-way relativities" does not exist as an output (the page shows loss ratios by segment) | Re-point D-5; Merit AI computes the one-way baseline itself |
| R8 | P6 | M5 overlaps Merit's stochastics (stoch/, v10.3.0): the same GPD fit, per client and layer-driven. D-7's cap unit: Merit's is life x UW year per policy (tools/basis.py), so a member on two policies is two units | M5 builds only the pooled threshold study and excess frequency; D-7 names the unit |
| R9 | P3 | Stream 7 says "launchers as in Merit"; Merit now has a browser page (GC UI kit) and a report builder with a fixed cover and basis of preparation. CLAUDE.md here says no GUI | Owner decides whether Merit AI adopts them |
Still true: Merit's PNLR has no input for an external loss ratio (D-6); no rate-change history is held (M6).

Open questions for the owner (defaults in use):
| # | Question | In use |
| --- | --- | --- |
| Q1 | **DECIDED 2026-11-16: a Flag (signed), not a re-run.** DONE in Merit v7.3.2 (2026-10-25, ete-dashboard a350841): both run manifests carry `contract_version`. Open part: a run from Merit v7.3.1 or earlier (no stamp): re-run on v7.3.2 before pooling (recommended; G1.1 missing-stamp level -> Stop, as SPEC) or accept with a signed Flag? | Missing stamp = FLAG (decided) |
| Q2 | Merit's FOB list has no Pharmacy class. Proposed: Out-Patient lines at a Pharmacy provider = Pharmacy; a TPA with no pharmacy provider type = "OP incl. pharmacy". Also confirm the six group codes and the FOB -> group map | Proposed |
| Q3 | Merit FOB values outside the six groups (Psychiatry, Alternative Medicine, Wellness & Preventive, Assistance, Other): which group, if any? | Unmapped (G2.3 counts them) |
| Q4 | Government-funded schemes are excluded (D-1): which Merit field identifies them? | Open |
| Q5 | Mandatory-basic segment (EBP / Basic): which field or network marks it beyond AAFIYA APN (Enhanced EBP)? | Proposed |
| Q6 | P1 acceptance says "every gate check fails on purpose". Built in P1: G1.1 and G1.4 (each with its cases); the other 46 are registered and must each add cases when their phase builds them (enforced by test). Accept this reading? | As stated |
| Q7 | AAFIYA "APN Edge / Essential": one network or two names? | Only the literal name maps |
| Q8 | **DECIDED 2026-11-16: 0.01.** G1.2 tolerance for the member-month fan-out (Merit manual 3.13 "0 within rounding, < 0.01") | 0.01 (decided) |
| Q9 | Disclosure class for trend rates, completion factors and provider / diagnosis indices: loss-cost (3 / 50% / 500 LY)? | Loss-cost (proposed) |
| Q10 | Merit change request bundle | (a) done in v7.3.2; nothing else open |
| Q12 | Merit IP4-11 (2026-10-31): (a) a run stamped IP4-9 or IP4-10: re-run on Merit v7.7.0+ before pooling, or accept with a signed Flag? (b) should the pool see business a cedant's scope register EXCLUDEs (the *_excluded twins), or the CAP excess (PayerShareExcess), or only the main tables as written? | (a) G1.1 refuses them (Stop). (b) Main tables only |
| Q13 | Merit IP4-13 (2026-11-15): (a) a run stamped IP4-11 or IP4-12: re-run on Merit v8.0.9+ before pooling, or accept with a signed Flag? (b) Opt_1..Opt_5 (raw cedant text): keep them out of the pool (proposed: not on the P2 allowed-column list), or allow named ones? (c) should the pool use the reinsured shares (ReinsuredPct, CededPct) at all, or stay on the 100% basis? | (a) G1.1 refuses them (Stop). (b) **DECIDED 2026-11-16: kept out of the pool** (not on the P2 allowed-column list; the export drops them). (c) Not used; open |
| Q11 | Merit v7.5.0 (IP4-9): (a) a Merit v7.4.0 run (IP4-8): re-run on v7.5.0 before pooling, or accept with a signed Flag? (b) BF lag-0 ultimates in monitoring: label them as assumption-based (Method "BF:"), or leave them with the other immature months? | (a) G1.1 refuses IP4-8 (Stop). (b) Treated as immature months, no label |

## Next step
1. Done 2026-10-25 18:05: repository mtamsyed-gc/merit-ai created; main = e1c9429 (P1).
2. Owner: run `launchers\00_Self_test.cmd` and `01_Run_tests.cmd` on the laptop after installing requirements.txt.
3. Owner: answer Q2-Q5 (needed by Stream 2), Q6, Q7, Q9, Q11, Q12, Q13 (a) and (c). Q1, Q8, Q13 (b) decided 2026-11-16.
4. P2 Pool v1: Stream 1 submission export + anonymisation (pool IDs, keyed hashes, allow-list) and Stream 2
   comparability, with G1.2, G1.3, G1.5-G1.8 and G2.1-G2.7 built and fail-on-purpose tested.
