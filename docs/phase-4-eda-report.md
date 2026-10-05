# CommerceLens Phase 4 — Exploratory and business findings

Analysis date: 2026-10-05. Historical anonymized Olist version 2; not a live
2026 business. Phase 4 explores the evidence and proposes investigations.
Official KPI definitions, reusable analytics marts and API contracts remain Phase 5.

## Decision brief

The strongest observed relationship is between late delivery and low review scores.
The geographic and monthly delivery patterns identify where to investigate that
relationship. Category concentration supports focusing assortment analysis on a
manageable set of categories, while product-level value is considerably more diffuse.
Observed repeat ordering is low, but it cannot establish marketplace lifetime retention.
These findings justify further investigation and controlled interventions; they do
not estimate the causal effect or financial return of an operational change.

| Priority | Supported observation | Investigation/action | Confidence and constraint |
| --- | --- | --- | --- |
| 1 | Low scores: 62.41% of late-calendar review pairs versus 9.28% on-time | Examine promise accuracy, handoff/carrier bottlenecks and customer communication; evaluate interventions prospectively | Strong descriptive association; similar under single-review sensitivity; selection/confounding remain |
| 2 | Cross-state median delivery 12.78 days versus 6.55 within-state | Compare route, carrier, promise and seller/category mix before revising estimates | Strong historical difference; distance and carrier identity unavailable; not a causal state-boundary effect |
| 3 | March 2018 has 1,328 late of 7,003 eligible delivered orders (18.96%) | Investigate the period using operational records and compare geography/category composition | Observed spike; its cause is unverified; acquisition/source coverage may affect trends |
| 4 | Ten categories account for 62.36% of item price; top 100 sellers for 45.06% | Prioritize category and seller support reviews using adequate sample sizes | Exact source value concentration; no margin, stock, traffic or seller-responsibility inference |
| 5 | Office furniture has 18.86-day median delivery and freight/item-value ratio 25.03% | Review packaging, freight economics and delivery promises on matched routes | 1,254 eligible orders; category orders overlap and outcomes are order-level |

## Source, reproducibility and trust boundary

Read [the initial dictionary](data_dictionary/initial.md), [quality warnings](data-quality-report.md),
[warehouse contract](decisions/0003-warehouse-contract.md), [audit debt](governance-audit.md)
and [exploratory plan](phase-4-plan.md). Nine immutable CSVs contain 1,550,922
source rows. The accepted warehouse preserves their content; analysis reads those
same source bytes locally to avoid repeated views-heavy database scans. No warehouse
query, credential use, reload, grant, migration or infrastructure tuning is needed.
This is not new verification of live warehouse state or its workload readiness.

The runner [src/analysis/eda.py](../src/analysis/eda.py) checks every source checksum,
manifest identity, row digest and exact money before and after analysis. Literal
IDs/ZIPs stay strings in memory; no identifiers or review text are exported. Original
CSV row order preserves reproducibility; immutable hashes provide lineage to the
accepted source ordinals without exporting row-level data. All generated runs remain
under unique ignored `.artifacts/phase-4/<UUID>` paths, without overwriting old runs.
[Aggregate evidence](phase-4-eda-results.json) contains complete domain tables.

```powershell
Set-Location 'D:\My Projects\CommerceLens'
.venv/Scripts/python.exe -B -m src.analysis.eda
```

Run twice; use the printed fresh result paths with
`scripts/verify_phase4.py FIRST/results.json REPLAY/results.json --receipt FRESH.json`.
Acceptance compares identical result bytes, accepted historical warehouse totals,
17 aggregate partitions and privacy fields. A new receipt path must not already exist.
Use the installed locked environment; do not implicitly synchronize/remove packages.
Synthetic tests are `tests/test_phase4_eda.py`. Safe retained full-suite instructions
remain in [CONTRIBUTING](../CONTRIBUTING.md). See [verification](phase-4-verification.json)
for actual dates, counts and retained paths rather than assuming commands ran.

## Exploratory contracts and denominators

| Question | Grain and eligibility | Exclusions/interpretation |
| --- | --- | --- |
| Sales volume/source value | All 99,441 orders and all 112,650 items; purchase month uses naive source timestamp | All statuses retained; delivered-only value shown separately; price is not profit or recognized revenue |
| Monetary totals | Integer BRL cents parsed from strict source Decimal text; item price, freight and payment components separate | Never sum float staging money; missing child amount remains null, real zero remains zero; ratios/quantiles are descriptive floating-point outputs |
| Order enrichment | One order; independently sum items/payments/reviews before left joins | Missing families retained; keys and mandatory dimension membership fail closed; no child cross-product |
| Products/categories | Item value attributed once to its product/category; category operations use one category/order association | An order may appear in several categories; category order counts/outcomes must not be summed into platform totals |
| Customers | Distinct `customer_unique_id`, with all-status and delivered-status order counts | Source `customer_id` is order-linked; no arbitrary current address; unequal follow-up, same-day purchases and other channels are unobserved |
| Sellers | Item value per seller; operations use unique seller/order association; distributions reported for >=100 eligible delivered orders | Multi-seller orders overlap; delivery is order-level, not proof of seller responsibility; no individual identifiers exposed |
| Geography/routes | Purchase-associated customer state; route is any seller state differing from that state, collapsed to one order | Orders without items absent from route comparison; no raw geolocation join, representative point or distance estimate |
| Payments | Every `(order_id, payment_sequential)` component, including zeros/undefined method | Methods can overlap at order grain; installment count is not number of components or a settlement schedule |
| Delivery duration | Delivered status with purchase and actual delivery present and non-reversed; elapsed seconds/86,400 | 96,470 eligible of 96,478 delivered orders; eight missing actual timestamps; other lifecycle intervals have their own valid-pair denominator |
| Lateness | Same eligible delivered set; actual > estimate versus actual calendar date > estimated calendar date | Source timestamps have no declared timezone; same-day delivery after estimated midnight changes classification; official policy not selected |
| Reviews | All `(review_id, order_id)` pairs; low score defined exploratorily as 1–2 | No canonical review; late association uses reviewed eligible delivered orders; single-review orders are a sensitivity sample, not selected-review policy |

## Sales: growth with important observation-window boundaries

Purchase timestamps span 2016-09-04 21:15:19 to 2018-10-17 17:30:18.
There are 25 observed purchase months; November 2016 has no rows and is not silently
filled. January 2017 has 800 orders and November 2017 has 7,544, the largest observed
month. The latter rises from 4,631 in October 2017 (62.90%). January–August 2018
monthly counts are 6,167–7,269. This supports H1's growth pattern through the earlier
middle window, not steady growth across every month or a proven seasonal effect.
November's timing alone does not demonstrate a Black Friday mechanism.

September/October 2018 contain only 16/4 orders, none delivered. Early 2016 coverage
is also sparse. Treat these as source-window/status warnings rather than a 2026
business collapse or clean full-year demand series. Even the dense middle months
are not certified complete marketplace demand: impressions, lost demand, source
sampling and stock are absent. No forecasting model is trained in this phase.

| Source component | Exact BRL total | Meaning |
| --- | ---: | --- |
| Item price | 13,591,643.70 | Sum of source item prices, all statuses |
| Item freight | 2,251,909.54 | Sum of source item freight amounts |
| Payment value | 16,008,872.12 | Sum of every source payment component |
| Delivered-status item price | 13,221,498.11 | Status sensitivity, not official recognized revenue |

Median item price is BRL 74.99 versus mean BRL 120.65; maximum BRL 6,735.00.
Median order item-price sum is BRL 86.90 versus mean BRL 137.75 among 98,666
orders with items; 775 absent-item orders are excluded from that distribution.
The skew means a mean alone hides the common basket. Aggregate freight/item-price
ratio is 16.57%, while median order ratio is 22.44% and its 90th percentile 62.25%.
These are different weightings and neither measures profitability or actual shipping cost.

## Products and categories: concentration is at category scale

H2 is qualified: the top five categories contribute 39.74% and top ten 62.36%
of source item price. Top ten products contribute only 3.32%; top 100 contribute
13.48% across 32,951 source products. Category focus is supported more strongly
than an assumption that a handful of products dominates the marketplace.

| Source category | Item price BRL | Items | Category/order associations | Eligible delivery orders | Calendar-late orders |
| --- | ---: | ---: | ---: | ---: | ---: |
| beleza_saude | 1,258,681.34 | 9,670 | 8,836 | 8,647 | 649 |
| relogios_presentes | 1,205,005.68 | 5,991 | 5,624 | 5,493 | 406 |
| cama_mesa_banho | 1,036,988.68 | 11,115 | 9,417 | 9,272 | 689 |
| esporte_lazer | 988,048.97 | 8,641 | 7,720 | 7,529 | 495 |
| informatica_acessorios | 911,954.32 | 7,827 | 6,689 | 6,529 | 417 |

The top five ranking is unchanged when restricted to delivered-status item value.
Unknown category remains a separate reporting label; it is not a source repair.
610 products lack category and 13 have a present untranslated category. Literal
Portuguese categories avoid silently losing untranslated products.

H8 identifies investigation candidates, not an estimated freight effect. Among
categories with >=1,000 associated orders, electronics has freight/item-price ratio
29.07% (2,550 orders), office furniture 25.03% (1,273), and furniture/decor 23.67%
(6,449). Office furniture's eligible median delivery is 18.86 days, versus 10.22
platform-wide; 101/1,254 eligible orders are calendar-late (8.05%). Electronics'
192/2,517 is 7.63%. Compare category, promise and route mix before attributing these
patterns to weight, packaging or seller behavior. No product-level return, margin,
inventory, conversion or quality measure exists.

## Customers: limited observed repeat activity

H3 is supported descriptively: 2,997/96,096 identities (3.12%) have more than one
source order. Using delivered status only gives 2,801/93,358 (3.00%). The median
and 90th percentile orders per identity are one; maximum is 17. Distinct source
order-customer records would have concealed this repeat activity.

This is observed repeat ordering within the extract, not lifetime retention, churn,
customer acquisition efficiency or loyalty. Customers enter at different times;
late-window customers have little follow-up. Identity coverage outside Olist and
multiple-channel purchases are unknown. Phase 7 owns formal cohorts, RFM and
segmentation; this phase does not set retention targets or create customer profiles.

## Sellers: concentration with attribution limits

H4 is supported: top ten of 3,095 sellers account for 13.15% of item value;
top 100 account for 45.06%. There are 100,010 seller/order associations, exceeding
98,666 orders with items because some orders have multiple sellers.

Only 210 sellers meet the exploratory >=100 eligible delivered-order threshold.
Their unweighted seller calendar-late-rate median is 5.70%, interquartile range
3.82–8.58%, 90th percentile 11.42%, and maximum 19.02%. This is a distribution of
seller-associated order rates, not the platform rate or a significance ranking.
The threshold is a support screen, not a confidence guarantee; seller size, route,
category and purchase period differ. Investigate high-volume associations using
matched comparisons and seller-specific uncertainty before intervention or blame.
Seller IDs are intentionally omitted from the shared report.

## Geography: concentration and longer cross-state delivery

São Paulo has 41,746/99,441 orders (41.98%) and BRL 5,202,955.05 item value.
Rio de Janeiro has 12,852 orders and Minas Gerais 11,635. Purchase-associated
source states are used; no current customer address is invented.

| Route population | Orders with items | Eligible delivered orders | Median elapsed days | Calendar-late count/rate |
| --- | ---: | ---: | ---: | --- |
| All sellers in customer state | 35,353 | 34,575 | 6.55 | 1,563 / 34,575 = 4.52% |
| Any seller outside customer state | 63,313 | 61,895 | 12.78 | 4,971 / 61,895 = 8.03% |

H5 is supported as an association: median difference 6.22 days and calendar-late
rate difference 3.51 percentage points. State crossing is a coarse proxy, not
measured distance, carrier capability or a causal treatment. For customer states,
SP has 1,820/40,494 calendar-late eligible orders (4.49%) and RJ 1,495/12,350
(12.11%). These are priorities for route/mix/promise investigation, not regional
service quality rankings adjusted for confounding.

All 1,000,163 geolocation observations remain source evidence. Of 19,015 observed
ZIPs, 8,556 have multiple literal cities and eight multiple states. There are 278
customer rows and seven seller rows without geolocation coverage. The warehouse
union ZIP dimension has 19,177 prefixes, a different denominator from observed
geolocation ZIPs. Duplicate points (261,831 excess duplicates) and 31 broad-box
flags remain warnings. No coordinate selection, geolocation fanout, deduplication,
distance or precise coordinate API is introduced.

## Payments: components, methods and reconciliation differences

H6 is supported: credit cards contribute BRL 12,542,084.19 (78.34% of payment
value), with 76,795 components across 76,505 orders. Median installment count is
three for credit-card components. Boleto contributes BRL 2,869,361.27 across 19,784
components/orders. Voucher has 5,775 components but only 3,866 orders; payment
methods and order counts can overlap. 2,961 orders have multiple components.
There are 52,546 one-installment components across all methods; do not treat that
count as unique one-installment orders or as credit-card-only activity.

Retain nine zero-value components, two zero-installment components and three
`not_defined` components. Among 98,665 orders with both items and payment records,
98,089 match item price plus freight exactly in cents; 576 differ. Signed summed
difference is BRL 2,870.39 and summed absolute difference BRL 3,271.95. This
comparison excludes missing families; it differs from subtracting platform-wide
totals. Differences are observations, not proof of rounding, installment charges,
fraud, refunds or loss. No payment settlement/accounting policy is invented.

## Logistics and reviews: strongest association and policy sensitivity

There are 96,478 delivered-status orders, 96,470 with valid purchase-to-delivery
intervals. Median elapsed delivery is 10.22 days, mean 12.56, 90th percentile
23.10, maximum 209.63. Approval-to-carrier uses 95,112 valid intervals (1,366
delivered orders excluded); median 1.85 days. Carrier-to-customer uses 96,446
(32 excluded); median 7.10. Those denominators differ, so their medians/means must
not be added to manufacture a complete lifecycle decomposition.

Calendar lateness is 6,534/96,470 (6.77%); timestamp lateness is 7,826/96,470
(8.11%). The 1,292-order difference reflects same-calendar-day arrivals after
estimated midnight. A business promise policy must be explicit in Phase 5.
March 2018 calendar lateness is 18.96%, February 14.13%, November 2017 12.40%,
and June 2018 1.16%. No unobserved operational incident is asserted as their cause.

All 99,224 review pairs have mean score 4.086; 57,328 have score five and 14,575
score one or two. There are 547 multiple-review orders and 768 orders without
reviews (including 646 delivered-status orders). Review absence is not satisfaction
and paired respondents need not represent all buyers.

| Exploratory comparison | Low-score numerator/denominator | Low-score rate | Descriptive Wilson 95% bounds |
| --- | --- | ---: | --- |
| Calendar on-time, all review pairs | 8,346 / 89,944 | 9.28% | 9.09–9.47% |
| Calendar late, all review pairs | 4,000 / 6,409 | 62.41% | 61.22–63.59% |
| Calendar on-time, single-review orders | 8,227 / 88,946 | 9.25% | 9.06–9.44% |
| Calendar late, single-review orders | 3,962 / 6,353 | 62.36% | 61.17–63.55% |
| Timestamp on-time, all review pairs | 8,186 / 88,653 | 9.23% | 9.04–9.43% |
| Timestamp late, all review pairs | 4,160 / 7,700 | 54.03% | 52.91–55.14% |

H7 is supported under both lateness definitions and the single-review sensitivity.
Calendar difference is 53.13 percentage points (relative rate about 6.73); paired
mean score is 2.27 late versus 4.29 on-time. The effect size is operationally large
within this sample. No multiple-testing p-value or causal inference is offered.
Wilson bounds characterize binary-count precision, not population generalizability;
all-pair dependence, repeated customers, selection and correlated operations limit
inferential interpretation. Single-review sensitivity addresses one dependence
source but does not remove the others. Geography, category, seller, purchase period,
promise length and other unobserved problems may confound the association. Review
events can precede final delivery, so temporal ordering does not prove that a late
arrival caused a score. Neither review score nor actual delivery is available at
order time; future delivery-risk features must exclude this leakage.

## Limits and next-phase decisions

All 29 documented source warnings remain; no eligibility choice repairs raw data.
Warnings overlap and must not be added into a count of unique bad orders. The
extract lacks profit, commission, cost, returns/refunds, stock, marketing exposure,
carrier identity, full customer history and treatment assignment. Historical
associations and exploratory screens do not establish current operational targets,
statistical population sampling or guaranteed savings.

Phase 5 must select status eligibility, exact-money API serialization, missingness,
review weighting and promise-clock policies in one KPI dictionary; preserve
denominators and overlapping category/seller associations. Q01 must measure actual
API query projections, filters, concurrency, capacity and budgets before tuning.
No API analytics or official marts are created by this report.

E01–E10 and the current audit's concrete gates remain maintainer-owned: dev-only
unpatched braces/ESLint exception; AnyIO warning; disabled npm scripts; batch/report
lifecycle and future volume; downstream eligibility; protected backup/exposure;
actual consumer auth/API/UX/E2E; remote CI/branch rules; owner license; gradual
report typing. Strict source-date review precedes any new version; precise
coordinates precede their API use. No populated backup/PITR, public security,
deployment or production-readiness claim. Both Supabase projects, private recovery
settings/certificates, immutable source, C fallback/three drafts and every generated
artifact remain retained. Any deletion needs specific informed owner approval.
