# Merit AI

Pooled UAE medical benchmarks and predictive models, built on the standard tables Merit produces for each
client run. Merit AI only reads Merit's outputs; it never changes Merit.

- **What and why:** [Project Brief](https://claude.ai/artifact/E7LLAKRdSzRxNtkRJ9yC1v)
- **How, step by step, with every gate and decision:** [Implementation Path](https://claude.ai/artifact/CXpt27kyqoqk3K3cqjFDgj), exported here as `SPEC.md`
- **Where the build is:** `HANDOVER.md`

## How to run (Windows, after installing the packages)

1. Install once, in a normal PowerShell window: `py -m pip install --user -r requirements.txt`
2. Double-click `launchers\00_Self_test.cmd`. It runs the five steps below on made-up data and should end with
   `SELF-TEST PASSED`.
3. Double-click `launchers\01_Run_tests.cmd` to run every test. It should end with `ALL PASS`.

## What the self-test does, in plain terms

| Step | What happens | Why it matters |
| --- | --- | --- |
| 1 Control files | Reads the gate list, thresholds, network tier map and disclosure rules, and checks they are complete and consistent | Every number a gate uses comes from these files, so a wrong file would silently change every result |
| 2 Merit contract | Checks the stored copy of Merit's table list is exactly the version Merit AI was built for | Merit AI must read only what Merit promises to write |
| 3 Synthetic pool | Writes six fictitious insurers as if each had run Merit, with effects planted on purpose (network, age, region, trend, large claims, insurer and group differences, match rates) | Models will later have to find these known answers before they touch real data |
| 4 Gate G1 | Runs the ingest checks built so far on each fictitious insurer | Shows the gates work end to end |
| 5 Gate report | Writes `out\selftest_reports\G1_selftest.xlsx` | The report a reviewer reads: one row per check, its result, what it means and what to do |

Expected: every insurer shows **PASS (incomplete)** on G1. The synthetic runs carry Merit's contract version stamp
(Merit v7.3.2 or later); "incomplete" means the G1 checks of later phases are not built yet.

## Reading a gate report

| Status | Meaning | What you do |
| --- | --- | --- |
| PASS | The check passed | Nothing |
| STOP | A Stop check failed; the stream halts | Fix the cause and re-run. A Stop can never be signed off |
| FLAG | A Flag check failed | Review it; continue only after the named signer records a sign-off and a reason |
| INFO / AUTO | Recorded for the reader, or handled automatically | Nothing |
| NOT_BUILT | The check belongs to a later build phase | Nothing yet; the gate is not complete until it is built |

## Folder map

| Folder | Holds |
| --- | --- |
| `control/` | Gate register (48 checks), thresholds, network tier map and other pool vocabulary, disclosure rules |
| `contract/` | Pinned copy of Merit's output contract and its fingerprint |
| `meritai/` | The code: contract reader, control loader, synthetic generator, gate engine, checks |
| `synth/` | The planted effects of the synthetic pool (`plant.json`) |
| `launchers/` | Numbered double-click launchers |
| `tests/` | The test suite |
| `out/` | Created when you run anything; never committed |

## Data rule

This repository holds code, settings and made-up data only. Real pool data lives only on the GC laptop and is
never committed here.
