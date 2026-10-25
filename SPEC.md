# UAE Medical Predictive Analytics — Implementation Path

Oct 25, 2026 · @etam

This path takes the predictive analytics capability from a cleared governance gate to a client offering. It has seven build streams. Each stream must pass a numbered gate before the next one consumes its output. It follows on from the [Project Brief](https://claude.ai/artifact/E7LLAKRdSzRxNtkRJ9yC1v), whose workstreams 4.2 to 4.6 it expands.

## How to read this document

The reader is a pricing actuary who knows the methods but does not write code. Each stream has the same five parts:

1. **Purpose:** one sentence on why the stream exists.
2. **Steps:** numbered, in build order.
3. **Gate:** the checks that must pass, with a proposed threshold and the action on failure.
4. **In plain terms:** a short note explaining the technical idea without code.
5. **Outputs:** the tables or pages the next stream reads.

Thresholds marked *proposed* are starting values for the owner to confirm. They are not settled business rules until recorded in the decisions log (section "Decisions needed").

### Glossary

| Term | Plain meaning |
| --- | --- |
| Pool | The combined, anonymised data of all participating cedants, held in one store. |
| Cell | One combination of rating factors, for example "Dubai, age 30–39, female, Network A". |
| Exposure (life-year, LY) | One member covered for twelve months. Two members for six months = 1 LY. |
| Credibility (Z) | A weight between 0 and 1 saying how far to trust a client's own experience versus the pool. |
| Bühlmann-Straub | A credibility formula that sets Z from the client's volume and how much clients genuinely differ from each other. |
| GLM | Generalised linear model: a regression that estimates the effect of each factor (age, network …) while holding the others constant. |
| Relativity | A factor's multiplier against a base cell. 1.25 = 25% more costly than the base. |
| Offset | A known quantity (here, exposure) fed into a GLM so it models a rate, not a count. |
| Backtest / holdout | Fit on older data, predict a period the model has not seen, then compare with actual. |
| A/E | Actual divided by expected. 1.00 = the prediction was right on average. |
| Lift / Gini | How well a model ranks risks from best to worst. Higher = better separation. |
| Drift | The data or the market moving away from what the model was fitted on. |
| Champion / challenger | The live model (champion) and a candidate replacement (challenger), compared on the same holdout. |
| Contract | The fixed list of tables and columns Merit promises to produce. This project reads only that list. |
| Gate | A set of automated checks. A failed Stop check halts the stream; a Flag lets it continue but must be signed off. |

## Scope and starting assumptions

Governance and permissions (Brief 4.1) are treated as passed. That means the following are in hand:

- the legal basis to pool each participating cedant's data;
- an anonymisation standard;
- a minimum-cell rule for anything shown to a client;
- an access model.

The pool is UAE medical only (DHA, DOH, MOH regimes). Other markets get their own pools later and are never mixed with it.

### Design principles

1. **Read Merit, never change it.** The project lives in its own repository and reads only Merit's output contract. The contract version is checked on every load, as Pricing-workbench does.
2. **Learn on the pool, apply per client.** Patterns are estimated on the pooled data. Each client's result blends its own experience with the pool by credibility.
3. **Nothing leaves a stream unchecked.** Every stream ends at a gate. A Stop check halts the stream. A Flag lets it continue but needs a named sign-off.
4. **Every number is traceable.** Each output row carries the pool snapshot, model version and assumption set that produced it.
5. **Deterministic and reproducible.** The same pool snapshot and the same versions give the same outputs. Random steps (bootstraps) use a recorded seed.
6. **Degrade, don't break.** A thin cell falls back to a coarser level or to the pool. It is labelled as such, never silently filled.
7. **Plain-language by default.** Every client-facing figure ships with a one-line explanation and its credibility level.
8. **Synthetic first.** Each model is first proven on synthetic data with planted effects. Only then is it run on the pool.

### Out of scope for v1

- Member-level underwriting decisions and real-time scoring.
- Life business.
- KSA and other markets.
- Machine-learning models that cannot be explained factor by factor (for example gradient boosting). These are a possible challenger in a later version, never the champion in v1.

## Architecture

&#91;embedded content: architecture · 7 streams, 7 gates\]

Data only moves down the page, and only through a gate. Benchmarks reach clients directly after G3. Predictions need the longer route through G4 to G7. The new repository reads Merit's outputs and never writes back to Merit.

## Stream 1 — Portfolio data store

**Purpose:** turn each cedant's completed Merit run into an anonymised, versioned submission. Only submissions that pass gate G1 enter the pool.

### Steps

1. **Set up the repository.**
   - Create a separate repository (working name `mr-predictive`), using the same pinned packages as Merit: numpy, pandas, DuckDB, pyarrow, openpyxl, xlsxwriter.
   - Keep a pinned copy of Merit's `model_contract.json`, with the contract version it accepts.
   - All settings live in JSON control files, never in code.
2. **Write the submission export.** A script reads one finished Merit run folder (`04_Outputs\parquet`). It takes only the contract tables the pool needs:
   - `dim_life`, `fact_member_month`, `fact_claims` (with the IBNR and IBNP ultimates);
   - `cf_selected`, the recon tables, the run manifest, and an exceptions summary.
3. **Anonymise in a fixed order.**
   - **Cedant:** the name is replaced by a pool ID. The ID ↔ name key file is held separately, with restricted access, and never enters the pool.
   - **Member and policyholder keys:** replaced by a keyed one-way hash (HMAC-SHA256) with a secret per cedant. The same member gets the same token in every run of that cedant. The token cannot be reversed, and cannot be matched across cedants.
   - **Dates of birth** become age at each exposure month.
   - **Dates** are kept at month level.
   - **Free-text fields** are dropped.
   - **Providers** keep a standardised ID, type and region. Names are kept only if the anonymisation standard allows it.
4. **Tag every row** with:
   - pool ID, market, regulator and TPA;
   - valuation and extract dates;
   - data tier (T0–T3, as in SPEC §5);
   - Merit version and contract version;
   - submission ID and ingest time.
5. **Load and snapshot.**
   - Append to Parquet, partitioned by market / pool ID / valuation date, with DuckDB views over it.
   - A **pool snapshot** is an immutable list of the submissions it contains, with their file hashes. Every model run names the snapshot it used.
   - The "current" view holds the latest valuation per cedant. Earlier valuations stay for drift and development studies.
6. **Record the outcome.** Write an ingest register (accepted / rejected, the reason codes, who approved). Rejected submissions keep their reasons.

### Gate G1 — Ingest

| # | Check | Proposed threshold | On fail |
| --- | --- | --- | --- |
| G1.1 | Contract version equals the pinned version | Exact | Stop |
| G1.2 | Merit run's own checks passed: recon ties, FanDiff within rounding, no Stop exception codes | All pass | Stop |
| G1.3 | Claims match rate, count and amount | In-scope: ≥ 95% full; 85–95% restricted; < 85% reject (D-2) | Stop below 85%; restricted tag at 85–95% |
| G1.4 | No column outside the allowed list; pattern scan finds no Emirates ID, name, phone or e-mail | Zero hits | Stop |
| G1.5 | Rows and amounts in = out of the anonymisation step | Exact | Stop |
| G1.6 | Submission hash not already in the pool | Unique | Stop |
| G1.7 | Same cedant and valuation already present | — | Flag: replacing needs sign-off |
| G1.8 | Maturity: months of development since the latest UW year began | Reported | Info |

> **In plain terms:** the pool is only as good as its worst submission. G1 lets in only runs that Merit has already proven reconcile, and only after every identifier has been removed. The hash keeps the same member recognisable within one cedant's history, which claimant and policyholder models need, without anyone being able to work back to who it is.

**Outputs:** pool snapshot (Parquet + DuckDB), ingest register, rejected-submission log.

## Stream 2 — Pool quality and comparability

**Purpose:** make submissions from different insurers and TPAs mean the same thing before any statistic is computed. Then build the analysis tables every later stream reads.

### Steps

1. **Pool vocabulary.** A crosswalk control file maps each cedant's standardised Merit values to one pool list per factor:
   - network tier, region / emirate and regulator;
   - nationality group, policy type and relation;
   - benefit (FOB / FOC), provider type and ICD chapter.

   The tier names themselves are an owner decision. Unmapped values land in "Unmapped" and are counted, never guessed.
2. **Definition alignment.** Each submission declares its basis, and the pool converts to one standard:
   - premium with or without VAT and fees;
   - gross claimed vs payer share;
   - treatment of pre-adjudication claims;
   - fronted / ASO business;
   - currency (AED).

   A submission with an undeclared basis does not pass the gate.
3. **Maturity control.** Frequency and severity studies use developed (ultimate) claims. Incurred months whose completion factor is below the maturity threshold are left out of calibration. They still count in monitoring, labelled as immature.
4. **Benefit design.** Annual limit, co-pay and plan are carried where the data has them. Where they are missing, network tier is the proxy, and the output says so. Mandatory basic products (for example the DHA Essential Benefits Plan) are a separate segment, never blended with enhanced plans.
5. **Comparability profile.** Each submission's key metrics are compared with the pool on a robust scale (median and MAD): age mix, premium per LY, claims per LY, loss ratio, Not Available shares. This finds submissions that look different, which may be a data issue or a genuine risk difference.
6. **Dominance check.** For every benchmark or model cell, record each cedant's share of exposure. This feeds the minimum-cell rule and the leave-one-out tests in Stream 5.
7. **Analysis base tables.** Build two tables, both tied back to the snapshot:
   - **exposure:** member-month × factors;
   - **claims:** one row per claim with its developed amount, incurred month, benefit, provider and diagnosis.

### Gate G2 — Comparability

| # | Check | Proposed threshold | On fail |
| --- | --- | --- | --- |
| G2.1 | Base-table totals (LY, earned premium, reported and ultimate claims) = snapshot totals | Exact | Stop |
| G2.2 | Basis declared for premium, claims, fronted business | All declared | Stop for that submission |
| G2.3 | Unmapped share of exposure per factor | ≤ 2% pass; 2–10% Flag; > 10% factor excluded from models | Flag / exclude |
| G2.4 | Not Available share per factor | > 5% Flag | Flag |
| G2.5 | Submission outlier, robust z on burning cost per LY within market × policy type | \|z\| > 3.5 | Flag: review, never auto-drop |
| G2.6 | One cedant's share of a cell's exposure | > 50% | Flag (min-cell rule governs disclosure) |
| G2.7 | Immature incurred months excluded from calibration (CF below threshold, proposed 0.80) | Reported | Info |

> **In plain terms:** two TPAs can call the same thing by different names, or the same name for different things. Pooling without this step mixes apples and oranges, and the models then find "effects" that are only definitional. The outlier check does not delete anyone; it puts a person in front of the unusual submission before it shapes the market view.

**Outputs:** crosswalk files, basis register, comparability report per submission, analysis base tables (exposure, claims).

## Stream 3 — Benchmark layer

**Purpose:** publish market frequency, severity, cost, trend and development by segment, each with its credibility shown. Then let a client see where it sits against the market on its own mix. This is the first client-facing deliverable, and it needs no predictive model.

### Steps

1. **Define the benchmark cube.**
   - **Measures:** claim frequency per 1,000 LY, average severity, burning cost per LY, PMPM, earned and ultimate loss ratio, utilisation and cost per visit by benefit.
   - **Dimensions:** age band, gender, relation, regulator / emirate, network tier, policy type, group-size band, nationality group, benefit, provider type.
2. **Set a roll-up hierarchy per dimension**, for example single age band → 10-year band → all ages. A cell that fails credibility or disclosure is replaced by its parent. The level used is shown beside the value.
3. **Credibility of each cell.** Use limited-fluctuation credibility (the full-credibility standard is shown in the formula below):
   - Decided (D-3): p = 90%, k = 10%; CV is the severity coefficient of variation in the cell.
   - Partial credibility Z = √(n / n\_F), capped at 1.
   - Published value = Z × cell + (1 − Z) × parent.
   - Each cell also gets a 90% interval: Poisson for frequency, bootstrap for severity.
4. **Disclosure rule.** A cell is published to a client only if both hold:
   - it meets the disclosure class of its measure (D-4): loss-cost measures at least 3 cedants, none above 50%, at least 500 LY; premium and loss-ratio measures at least 5 cedants, none above 25%, at least 1,000 LY;
   - the client's own data is not the cell's majority.

   Suppressed cells are still used internally.
5. **Market trend index.** Fit calendar-month PMPM on developed months, split into frequency and severity.
   - Hold mix fixed (a GLM with a time term, or direct standardisation to the pool mix).
   - Add month-of-year seasonality.
   - Report an annual rate with its interval, by benefit and provider type.
   - It stays a **benchmark**. SPEC D22's 10% remains the pricing default until the owner decides otherwise (D-5).
6. **Development benchmark.** Pool completion factors by market × TPA × benefit, with the spread across cedants. Stream 6 uses them as the prior for small clients.
7. **Provider and diagnosis indices.** Cost per visit by provider relative to peers of the same type and region, adjusted for ICD chapter and benefit mix. Diagnosis-chapter cost and frequency by age and gender.
8. **Client positioning, mix-adjusted.**
   - Expected cost = Σ over cells of the client's exposure × pool rate.
   - The client's A/E = actual ÷ expected, with its interval.
   - Show the raw comparison too, but lead with the mix-adjusted one.
9. **Publish.** Benchmark tables are stamped with the snapshot ID, refreshed quarterly, and kept by version.

```latex
n_F = \left(\frac{z_{(1+p)/2}}{k}\right)^2 \left(1 + CV^2\right), \qquad Z = \min\left(1, \sqrt{n / n_F}\right)
```

### Gate G3 — Benchmark release

| # | Check | Proposed threshold | On fail |
| --- | --- | --- | --- |
| G3.1 | Cube totals = base-table totals | Exact | Stop |
| G3.2 | Disclosure rule on every client-visible cell | 100% compliant | Stop (cell suppressed) |
| G3.3 | Credibility Z shown on every cell | Z < 0.3 → shown as rolled up | Auto roll-up |
| G3.4 | Leave-one-cedant-out: change in a cell's value | > 15% | Flag "driven by one cedant" |
| G3.5 | Movement versus the previous snapshot | > 20% without a recorded reason | Flag |
| G3.6 | Trend interval width (90%) | > 10 points | Labelled indicative |
| G3.7 | Plausibility ranges set by the owner (frequency, severity, LR) | Inside range | Flag |

> **In plain terms:** comparing a young, mostly male workforce with the "market average" makes it look cheap even if it is not. The mix-adjusted A/E asks a fairer question: what would the market have paid for exactly this membership? Above 1.00, this client costs more than the market for the same people. The credibility weight stops a cell built on 40 claims from being presented with the same confidence as one built on 40,000.

**Outputs:** benchmark cube (with Z, level used, interval, disclosure flag), trend index, pooled development factors, provider and diagnosis indices, client positioning tables.

## Stream 4 — Predictive models

**Purpose:** fit a short ladder of explainable models on the pool. Each model is built, validated (Stream 5) and released on its own, in the order below. A later model may use an earlier one's output, never the reverse.

### The model ladder

| # | Model | Method | Answers | Minimum data (proposed) |
| --- | --- | --- | --- | --- |
| M1 | Trend and projection | Mix-fixed log-linear PMPM with seasonality, by frequency and severity; projected to the target period's mean incurred date (SPEC P5b) | What will cost per member be next year? | 24 developed months |
| M2 | Multivariate relativities | Poisson frequency GLM with log(LY) offset × Gamma severity GLM, per benefit group; large claims capped | How much does each factor change cost, holding the others fixed? | 20,000 LY, 5 cedants |
| M3 | Expected LR by policyholder | Bühlmann-Straub: M2 × M1 expected cost on the policyholder's own mix, blended with its developed experience | What LR should we expect at renewal for this group? | M2 released; 2 UW years per group |
| M4 | Reserve ranges | Over-dispersed Poisson bootstrap and Mack on triangles, pooled and per client | How uncertain is the IBNR? | 12 cohorts per triangle |
| M5 | Large loss and tail | Annual cost per claimant; threshold from the mean-excess plot; generalised Pareto fit; excess frequency per 1,000 LY by segment | What sits above a retention, for XoL and stop loss? | 50 claimants above threshold |
| M6 | Retention response (later) | Logistic regression on renewal vs rate change, size and LR | How does retention react to a rate increase? | Rate-change history: not yet held |

### Steps common to every model

1. **Specify before fitting.** Write a one-page model spec, signed by the owner before any code:
   - target, exposure measure and factors;
   - candidate groupings of levels;
   - large-claim cap;
   - holdout design;
   - acceptance thresholds.
2. **Prove on synthetic data.** Extend Merit's synthetic generator to plant known effects: relativities, a trend rate, a Pareto tail, a credibility structure. The model must recover them within the tolerance in its spec. This is a permanent test.
3. **Fit in controlled code.**
   - Estimation uses pinned statsmodels (GLMs) and scipy (GPD likelihood, distributions); Mack / ODP bootstraps and credibility formulas are written in-house with recorded seeds (D-8).
   - Each estimator is unit-tested against reference values computed independently once and stored with the tests.
   - Each fitted model is also refitted offline in R (glm()) and the coefficients compared, as G4's independent reference.
4. **Control for the cedant.** M2 includes cedant (or TPA) as a control factor. Relativities are then not distorted by which insurers write which segments. The cedant effect is dropped when applying to a client; Stream 6's credibility puts the client's own level back.
5. **Group and simplify.**
   - Merge adjacent levels whose relativities do not differ significantly.
   - Remove factors that do not improve the holdout fit.
   - Allow at most one interaction (age × gender) in v1.
6. **Validate.** Hand the fitted model to Stream 5 and record its results in the model inventory.
7. **Release.** Freeze the model version: coefficients, groupings, cap, snapshot ID and spec version. Write its outputs: relativity tables, projections, percentiles, each with a version stamp.

### Gate G4 — Fit (per model, before validation)

| # | Check | Proposed threshold | On fail |
| --- | --- | --- | --- |
| G4.1 | Recovers planted synthetic effects | Within spec tolerance (e.g. ±3% per relativity) | Stop |
| G4.2 | Estimation converged; no level with zero or near-zero exposure left in | Converged; each level ≥ 1% of exposure | Stop |
| G4.3 | Fitted totals = actual totals on the training data (GLM balance property) | Within 0.1% | Stop |
| G4.4 | Sign and shape plausible to an actuary (e.g. cost rising with age past 30) | Owner review | Flag: explain or regroup |
| G4.5 | One-way vs multivariate: large gaps explained by correlated factors | Gap > 15% needs a written reason | Flag |
| G4.6 | Parameter stability: 90% bootstrap interval per relativity | Width < 20% of the estimate, else group the level | Flag / regroup |

> **In plain terms:** a one-way table says Network A costs 30% more. But Network A may simply have older members. The GLM separates the two, so each relativity is the effect of that factor alone. The synthetic test is the equivalent of checking a spreadsheet against a hand calculation: the model is given data where we know the right answer and must find it.

**Outputs:** per model, a frozen version with its spec, fitted tables, synthetic-recovery report and fit diagnostics.

## Stream 5 — Validation and model governance

**Purpose:** prove each model predicts better than what is used today, on data it has not seen. Document it to Marsh McLennan model-risk standards, and watch it after release.

### Steps

1. **Two holdouts for every model.**
   - **Out-of-time:** fit on UW years up to E − 1, predict year E on developed claims.
   - **Out-of-cedant:** leave one cedant out, fit on the rest, predict the one left out. This mimics applying the model to a new client.
2. **Compare with a baseline**, never in isolation. The baselines are:
   - Merit's current one-way relativities and PNLR inputs;
   - the pool average;
   - the client's own last year.

   A model that does not beat the baseline is not released, however elegant.
3. **Measure by model type.**
   - **M1, M2:** A/E overall, by factor level and by cedant; decile lift and double-lift against the baseline; Gini.
   - **M3:** error of the blended LR against both pool-only and own-experience-only.
   - **M4:** the share of past actual run-offs that fell inside the predicted 90% range.
   - **M5:** fitted vs empirical excess above several thresholds; quantile plot.
4. **Independent review.** A reviewer who did not build the model re-runs it from the frozen version and checks the gate results. Writing support (for example a Claude review agent) is allowed, but the sign-off is a person's.
5. **Model card per model** (two pages, plain language):
   - purpose and approved uses;
   - **prohibited uses** (for example individual member decisions);
   - data and snapshot, method, limitations;
   - validation results, owner, next review date.
6. **Register** the model in the model inventory, with version, owner and risk rating.
7. **Monitor every new snapshot** (quarterly):
   - A/E by segment;
   - population stability index (PSI) on the factor mix;
   - realised vs projected trend.

   Breaches open a review ticket.
8. **Recalibrate** annually, or earlier on a monitoring trigger. The new version runs as a challenger beside the champion for one cycle before it replaces it.

### Gate G5 — Release

| # | Check | Proposed threshold | On fail |
| --- | --- | --- | --- |
| G5.1 | Out-of-time A/E, whole holdout | 0.95–1.05 | Stop |
| G5.2 | A/E per factor level with credible exposure (Z ≥ 0.5) | 0.90–1.10 | Flag: regroup or explain |
| G5.3 | Out-of-cedant error vs pool-average baseline | Not worse | Stop |
| G5.4 | Lift: Gini and double-lift vs current one-way approach | Strictly better | Stop |
| G5.5 | M3 blended error vs pool-only and own-only | Lower than both | Stop |
| G5.6 | M4 interval coverage on back-test | 80–97% inside the 90% range | Flag |
| G5.7 | Model card, inventory entry, independent sign-off | Complete | Stop |

### Monitoring triggers (after release)

| Trigger | Proposed level | Action |
| --- | --- | --- |
| PSI on any factor's mix | > 0.25 | Review; refit if A/E also moves |
| A/E by segment | Outside 0.90–1.10 for two quarters | Recalibrate |
| Realised vs projected trend | > 3 points a year | Refit M1 |
| New cedant share of pool exposure | > 20% in one refresh | Re-run G5.3 before use |

> **In plain terms:** a model always fits the data it was built on. The test that matters is the year it never saw, and the insurer it never saw. "Lift" asks whether the model sorts groups from cheap to expensive better than today's method. If it does not, it adds nothing and is not released. Monitoring is the equivalent of an A/E review on a reserving basis: it tells you when the model has gone stale.

**Outputs:** validation report per model, model cards, inventory entries, monitoring dashboard, champion / challenger log.

## Stream 6 — Client application

**Purpose:** turn pool models into one client's prediction. The client's own experience is blended with the pool's expectation, by how much credible data the client has. Every component of the blend is shown.

### Steps

1. **Prepare the client's data.** The client's data comes through Merit as today and passes G1 and G2 on its own, even if the client never joins the pool.
2. **Build a prior that excludes the client.** If the client is a pool member, its own data is removed from the pool before building its prior (leave-own-out). Otherwise its experience would be counted twice.
3. **Pool expectation on the client's mix.** For each cell of the client's exposure, combine:
   - the base rate;
   - M2 relativities;
   - M1 trend to the target period's mean incurred date.

   Summing gives the client's expected cost per LY. The large-claim cap is applied here, with the excess load added separately in step 6.
4. **Client's own experience.**
   - Developed claims, capped at the same threshold, trended to the same target date.
   - Where the client's development is thin, its completion factors are themselves blended with the pooled development benchmark from Stream 3.
5. **Credibility weight.** Use Bühlmann-Straub (formula below):
   - w is the client's earned LY.
   - K = expected process variance ÷ variance of hypothetical means. It is estimated from the spread of cedants in the pool, so the pool says how much clients really differ.
   - Applied in levels: market → client → policyholder (M3).
6. **Add the large-loss load.** The cost above the cap comes from M5's pool rate on the client's mix. A client's own excess experience is too volatile to blend.
7. **Projected LR.** Divide the blended cost by the client's projected premium at the proposed rate. Report:
   - a point estimate and a 90% interval;
   - a decomposition: pool expectation, client adjustment, Z, trend, large-loss load.
8. **Scenarios.** Overrides for trend, rate change and cap are typed into a run form, recorded with the output, and never change the released models.
9. **Optional hand-off to Merit.** Expected LR per rating group, with its pool Z, is written to a prior file. Merit's PNLR has no input for an external LR today (its Z weights the expiring year against the prior year), so using it needs a Merit change: an optional input, off by default. Decided in D-6: only after M3 passes G5.

```latex
Z = \frac{w}{w + K}, \qquad K = \frac{\text{expected process variance}}{\text{variance of hypothetical means}}, \qquad \hat{C} = Z \cdot C_{\text{client}} + (1 - Z) \cdot C_{\text{pool}}
```

### Gate G6 — Client output

| # | Check | Proposed threshold | On fail |
| --- | --- | --- | --- |
| G6.1 | Client data passed G1 and G2 | Pass | Stop |
| G6.2 | Every model used is released (passed G5) and not past its review date | All | Stop |
| G6.3 | Prior built without the client's own data | Verified by snapshot list | Stop |
| G6.4 | In the model's domain: client exposure in unmapped levels or levels with Z < 0.3 | ≤ 10% | Flag "partly outside model domain" |
| G6.5 | Decomposition adds up: pool expectation × client adjustment + large-loss load = result | Exact | Stop |
| G6.6 | Z in \[0, 1\] and consistent with volume (a small client cannot get Z > 0.9) | Owner rule | Flag |
| G6.7 | No other cedant's figure below the disclosure rule appears in the output | None | Stop |
| G6.8 | Interval and assumptions (snapshot, versions, overrides) printed with the result | Present | Stop |

> **In plain terms:** a group of 300 lives with a bad year is mostly noise; a group of 30,000 is mostly signal. Credibility turns that intuition into a number. K is the size at which a client's own data and the market get equal weight, and the pool estimates it from how much real insurers differ. Leaving the client out of its own prior avoids grading its homework with its own answers.

**Outputs:** client prediction tables (point, interval, decomposition), scenario log, optional PNLR input file.

## Stream 7 — Delivery and user experience

**Purpose:** make every output usable by an actuary who does not code, and safe to hand to a client. Every figure carries its credibility, its basis and a plain-language reading.

### Steps

1. **Launchers, not commands.** One numbered launcher per task, as in Merit:
   - `01_Ingest_submission`
   - `02_Refresh_pool`
   - `03_Build_benchmarks`
   - `04_Fit_models` (owner only)
   - `05_Client_prediction`

   Each prints progress in plain English and ends with a gate summary: PASS, FLAG or STOP, plus what to do next.
2. **Gate report.** Every run writes one workbook. It has a traffic light per check, the reason in plain words, the fix, and who must sign a Flag.
3. **Internal Power BI report**, a separate file reading the pool and model tables. Pages:
   - Pool health: snapshot, cedants, gate status.
   - Benchmarks.
   - Client position (mix-adjusted A/E).
   - Trend.
   - Relativities: one-way and multivariate side by side.
   - Expected-LR watch list.
   - Reserve ranges.
   - Tail and retentions.
   - Model health: A/E, PSI.
   - Assumptions and versions.
4. **Explanatory layer on every visual.** An info button gives three lines: *what this shows*, *how to read it*, *caveat*. The text comes from one glossary file, so wording is consistent and maintained in one place.
5. **Confidence badge on every figure.**
   - High: Z ≥ 0.7.
   - Medium: 0.3–0.7.
   - Low: below 0.3, shown greyed with the level it rolled up to.

   The badge levels are proposed for the owner to confirm.
6. **Client deliverables** from a fixed template:
   - cover and basis of preparation;
   - benchmark position;
   - prediction with interval and decomposition;
   - limitations;
   - disclaimer.

   Exported as PDF or Excel, with no other cedant's data below the disclosure rule.
7. **Narrative layer.** A LenAI / Claude summary reads only aggregated outputs, from a fixed prompt. An automated check confirms every number in the narrative exists in the output tables. A narrative with an unmatched number is not released.
8. **Documentation.**
   - User manual and admin guide.
   - Model cards.
   - An interactive walkthrough on a synthetic demo client (as Merit's manual).
   - A one-page "how to explain this to a client" note per model.

### Gate G7 — Deliverable release

| # | Check | Proposed threshold | On fail |
| --- | --- | --- | --- |
| G7.1 | Every figure in the deliverable ties to an output table (automated tie-out) | 100% | Stop |
| G7.2 | Every figure carries a confidence badge and its basis | 100% | Stop |
| G7.3 | Narrative numbers all found in outputs | 100% | Stop |
| G7.4 | Disclosure re-check on the final file | Pass | Stop |
| G7.5 | Peer review by a second actuary | Signed | Stop |

> **In plain terms:** the models are only useful if the person presenting them can defend each number. The badge, the info text and the decomposition let you answer "how sure are you?" and "where does this come from?" without opening any code.

**Outputs:** launchers, gate reports, internal Power BI report, client pack template, narrative, documentation set.

## Gate register

Seven gates, 48 checks. Nothing reaches a client without passing G1 → G3 (benchmarks) or G1 → G7 (predictions). The detail of each check sits in its stream; this table is the one-page view.

| Gate | Sits between | Protects against | Checks (Stop / Flag / Info) | Who signs a Flag |
| --- | --- | --- | --- | --- |
| G1 Ingest | Merit run → pool | Unreconciled runs, identifiers, duplicates | 8 (6 / 1 / 1) | Pool owner |
| G2 Comparability | Pool → base tables | Definitional differences read as risk differences | 7 (2 / 4 / 1)\* | Pool owner |
| G3 Benchmark release | Base tables → benchmark cube | Thin cells, disclosure breaches, one-cedant cells | 7 (2 / 3 / 0)\*\* | Lead actuary |
| G4 Fit | Base tables → fitted model | Bugs, non-convergence, implausible relativities | 6 (3 / 3 / 0) | Model owner |
| G5 Release | Fitted model → released model | Overfitting, no gain over today's method | 7 (5 / 2 / 0) | Independent reviewer |
| G6 Client output | Released models + client data → prediction | Out-of-domain use, double counting, disclosure | 8 (6 / 2 / 0) | Client actuary |
| G7 Deliverable | Prediction → client file | Untied figures, unsupported narrative | 5 (5 / 0 / 0) | Second actuary |

\* G2.3 can also exclude a factor. \*\* G3.3 and G3.6 roll up or label automatically.

### Rules that apply to every gate

1. **One result per check:** Stop, Flag or Info. A Stop halts the stream. A Flag needs a named sign-off with a reason, stored in the gate report.
2. **Thresholds live in a control file,** with a version number. Changing one is a recorded decision, never an edit in code.
3. **Gates run automatically** at the end of every launcher. They cannot be skipped. An override is a signed Flag, never a bypass.
4. **Every gate check has a test** that makes it fail on purpose, on synthetic data.
5. **Gate reports are kept with the outputs** they cleared, so any figure can be traced to the checks it passed.

## Build sequence and acceptance

&#91;embedded content: build sequence · 7 phases, each closed by its gate\]

Each phase closes only when its exit gate passes on synthetic data and then on the pool. No dates are set: P3 can start as soon as P2's pool is in, and needs no model. P6 can run alongside P5 if a second builder is available.

The phases in text, so the exported copy (SPEC.md) carries them:

1. **P1 Foundations.** Repository, contract pin, synthetic pool, gate engine. Exit: every gate check fails on purpose in tests; launchers run end to end on synthetic data.
2. **P2 Pool v1 (Streams 1–2).** First 3–5 cedants anonymised and loaded. Exit: G1 and G2 pass for every submission; base tables tie to the snapshot.
3. **P3 Benchmarks (Streams 3, 7).** Benchmark cube, trend index, client pack v1. Exit: G3 and G7 on a pilot client, the first client-facing release.
4. **P4 Models I (M1, M2).** Trend projection and GLM relativities. Exit: G4 and G5; beats one-way tables on holdout, out-of-time and out-of-cedant.
5. **P5 Client application (M3, Stream 6).** Credibility blend and expected-LR watch list. Exit: G5.5 blend beats pool-only and own-only; G6 and G7 on a pilot renewal.
6. **P6 Models II (M4, M5).** Reserve ranges; tail for XoL and stop loss. Exit: G5.6 range coverage 80–97%; tail fit matches empirical excess.
7. **P7 Operate.** Quarterly refresh, annual recalibration, M6. Exit: monitoring triggers live; champion / challenger log kept.

### Working method for every phase

1. **Start** by restating the phase's acceptance criteria and the spec sections it touches.
2. **Build** synthetic tests first; each Stop check gets a test that fails on purpose.
3. **Run** the full test suite; all pass before every commit.
4. **Release** with a version number, release notes and an updated handover file, as Merit does.

## Decisions needed

All ten decisions were taken on 25 October 2026. Each DECIDED row overrides any *proposed* value stated earlier in this document. Nothing remains open.

| # | Decision | Proposed default | Needed by |
| --- | --- | --- | --- |
| D-1 | Pool vocabulary: network tiers, region / regulator grouping, benefit groups | DECIDED 2026-10-25: network = defined tiers, 7 tiers by position in each TPA's rate table (map below; a monitoring dimension, not burning-cost driven); region = 3 regulator regions (DHA / DOH / MOHAP), provider emirate + Outside UAE as a claims attribute; benefits = six groups, bundled pharmacy labelled not split; government-funded schemes excluded | Stream 2 |
| D-2 | Runs with match rate below 95%: reject, or admit as tier T2 for segment-level benchmarks only | DECIDED 2026-10-25: banded — ≥ 95% full use; 85–95% restricted (level benchmarks only, no member-attribute models); < 85% reject. Rate = matched ÷ in-scope claims (less pre-inception, out-of-cover, reversals); count and amount must both pass | Stream 1 |
| D-3 | Credibility standard (p, k), badge levels, minimum data per model | DECIDED 2026-10-25: p 90%, k 10% (n\_F = 271 × (1 + CV²); CV on capped severity); client K at policyholder level with floor / cap, cedant-level K reviewed at 10+ cedants; badges 0.7 / 0.3; M2 needs 5 cedants; other minimums as in the model ladder | Stream 3 |
| D-4 | Disclosure numbers: minimum cedants, maximum single-cedant share, minimum LY | DECIDED 2026-10-25: two-tier by measure: loss-cost measures 3 cedants / max 50% / 500 LY; premium and loss-ratio measures 5 / 25% / 1,000 LY; client the majority of a cell → leave-own-out if it still passes, else parent level | Stream 3 |
| D-5 | Market trend: benchmark only, or replace SPEC D22's 10% pricing default | DECIDED 2026-10-25: benchmark only now; once M1 passes G5, a governed default (90% interval < 4 points, corridor 5–15%, else 10%; annual reset; prospective items as documented overlays; needs a SPEC D22 / P5b change). Merit PNLR 8% vs D22 10% left until M1 | Stream 4 (M1) |
| D-6 | Client predictions written into Merit's PNLR assumptions workbook | DECIDED 2026-10-25: kept separate until M3 passes G5; then a Merit change request: optional pool-prior input (expected LR per rating group + pool Z) replacing the PNLR year-weighting when supplied, off by default (Merit byte-identical when off), input file cleared through G6 / G7 | Stream 6 |
| D-7 | Large-claim cap per benefit group | DECIDED 2026-10-25: per claimant per policy year, all benefits combined (excess allocated back pro rata); level from the M5 mean-excess / GPD study, then fixed in AED and indexed annually; provisional AED 500k until then, flagged in outputs; applied after development and trend (P5b order); distinct from P5b contractual-limit capping | Stream 4 (M2) |
| D-8 | Packages: numpy-only estimators, or approve and pin statsmodels | DECIDED 2026-10-25: statsmodels + scipy, pinned, Artifactory wheels confirmed by the owner; R glm() used offline as the independent reference for G4 / G5 | Stream 4 |
| D-9 | Hosting; who may run model fitting; who is the independent reviewer | DECIDED 2026-10-25: build and full testing on the owner's laptop (synthetic data only), then the pool runs on a GC laptop; owner = pool owner and model owner; SB = key custodian and model-fitting deputy, as GC policy allows (decided 25 October 2026); G5 independent reviewer = a GC actuary outside the build | Stream 1 / 5 |
| D-10 | Refresh and recalibration cadence | DECIDED 2026-10-25: ingestion any time; quarterly publication window, a new version only if new data adds ≥ 10% of pool exposure or a cedant's valuation moves on (else carried forward; versions labelled by quarter); annual recalibration + trend reset finished by April for mid-year renewals; Stream 5 triggers off-cycle | Stream 5 |

### D-1 network tier map (version 1, 25 October 2026)

Tiers follow the column order of each TPA's rate table. They are a starting point to monitor, not a burning-cost ranking. A new TPA's networks are placed by their equivalent column. Tables with fewer columns (E-Care) sit at the tiers they correspond to.

| Pool tier | NAS | NextCare | Mednet | AAFIYA | E-Care | Roll-up |
| --- | --- | --- | --- | --- | --- | --- |
| CN | CN | GN+ | Gold | Elite | — | Top |
| GN | GN | GN | Silver Premium | Diamond | — | Top |
| GN (excl. Mediclinic: own file, filed on GN) | GN excl. Mediclinic | GN excl. Mediclinic | Silver Classic | — | — | Top |
| RN | RN | RN | Green | Gold | — | Mid |
| RN2 | SRN | RN2 | Emerald | Plus | Classic | Mid |
| RN3 | WN | RN3 | Pearl | APN Edge / Essential | Green | Basic |
| VN | VN | RN3 (OP clinics only) | Silk Road | APN (Enhanced EBP) | Blue | Basic |

Notes:

- **GN excl. Mediclinic** is pooled as GN. It keeps its own label so it can be monitored separately.
- **AAFIYA APN (Enhanced EBP)** is a VN-tier network on a mandatory-basic product. It takes tier VN *and* stays in the separate mandatory-basic segment (Stream 2 step 4).
- **Roll-up** is the parent level a thin tier falls back to under G3.3. Top / Mid / Basic, decided 25 October 2026.
