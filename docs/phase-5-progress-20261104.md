# CommerceLens progress — 4 November 2026

Phase 5 remains partially complete. The main remaining product gate is proving
that the analytics layer returns consistent results within its resource limits.
The latest source candidate is verified offline but has not been adopted in the
database. Phases 1–4 and the required governance audit are complete. Phase 6, which
delivers the usable web MVP, has not started.

## Current position

| Area | Evidence and remaining work |
|---|---|
| Foundation, acquisition and warehouse | Complete baseline, including all nine source tables and 1,550,922 source rows; existing models and provenance preserved. |
| Exploratory/business analysis | Phase 4 report, independent reconciliations and repeatability verified. |
| KPI definitions | Versioned dictionary defines eligibility, exact money, completeness, reviews and lateness. |
| Analytical marts | Order and item KPI models are implemented and built. Baseline native acceptance exists. Later optimization candidates require their own acceptance before adoption. |
| API-facing query contracts | Parameterized queries, filters, pagination and exact response serialization implemented; this is not the integrated HTTP/web product. |
| Performance | Q01 remains open. The complete 16-case workload and concurrent pair have not passed. |
| Cross-consumer consistency | Independent dashboard/consumer reconciliation and final Phase 5 exit remain pending. |
| User-facing web product | Only the earlier scaffold/health endpoint exists. Integrated pages, live API/database flows and public deployment belong to Phase 6. |

The project has no effort-weighted completion baseline. Counting completed phases
or tests would give a misleading percentage: the web product and later customer,
predictive, decision-intelligence and production work differ greatly in size.

## What this session established

Resumed clean published `9eded40`. Prepared and reviewed a retained read-only
supervisor for all 83 existing native item-staging cases. Its offline guard checks
passed, including wrong-target rejection, forced rollback, deadline enforcement,
incomplete-result rejection and restoration checks. The 158 bound inputs include
the actual staging model, parsing helpers and installed generic test SQL.

The database run reached a shared fixture setup assertion: the backend SSL flag
was false where the older direct-connection fixture expected true. All 83 cases
therefore had setup errors; **none of their data-test bodies completed**. This is
not evidence of 83 SQL correctness failures. Independent catalog, access and
settings restoration passed; database and raw sizes were unchanged during the job.
No application source, test body, package or persistent database change was made.
The previous 1,986 offline passes, including 132 staging cases, remain historical
accepted evidence. See [native evidence](phase-5-item-staging-native-verification.json).

PostgreSQL's [SSL statistics](https://www.postgresql.org/docs/17/monitoring-stats.html#MONITORING-PG-STAT-SSL-VIEW)
describe the backend connection. Supabase documents
[verify-full session-pooler connections](https://supabase.com/docs/guides/database/psql).
The two-hop connection may explain the assertion mismatch, but actual client TLS
state was not separately measured. Verify it before adapting the fixture; do not
remove security assertions or substitute test results.

## Why Phase 5 has taken this long

1. **The performance blocker is real.** An earlier semantically verified candidate
   took 7.917 seconds, within the 10-second server limit, but used 565,272,576 bytes
   of temporary traffic, exceeding the 536,870,912-byte limit. Another used
   504,496,128 bytes, within that limit, but took 17.579 seconds. Neither passes
   both. These are individual samples, not full-workload acceptance or proof of a
   timing cause. See [first result](phase-5-shared-projection-full-source-verification.json)
   and [second result](phase-5-reference-reuse-verification.json).
2. **The cause was inside layered SQL planning.** A controlled comparison finally
   reproduced an estimate of 200 order groups through a WITH-containing subquery,
   versus 87,208 through an equivalent derived SELECT. That justified the latest
   staging rewrite, but an improved estimate does not prove runtime improvement.
3. **Optimizations must preserve business meaning.** Exact decimals, missing and
   invalid values, row multiplicity, lineage and independent reconciliation all
   matter. Several candidates were correct but still too expensive to accept.
4. **Environment and session interruptions added work.** Recovery-project pause,
   connection routing, restricted execution and usage-reserve stops required
   recovery and handoffs. Today's legacy SSL assertion is another harness issue.
5. **There was avoidable process overhead.** Numerous copied diagnostic runners,
   binding inventories and repeated setup/review/checkpoint cycles consumed time
   and allowance. The small planner-boundary comparison could have been isolated
   earlier. There is no reliable measurement of the share attributable to overhead.

## Shortest remaining route

First measure client TLS and backend connection state with a small, bounded,
read-only diagnostic. Resolve the fixture's connection-scope assumptions and run
all 83 native cases. Then verify all nine staging fields and downstream 15/70/26
field contracts on the full source, measure the candidate under existing limits,
and adopt only a verified change. Complete the 16 workload cases, concurrency,
independent consumer reconciliation and Phase 5 exit evidence afterward.

Prefer the smallest diagnostic that distinguishes competing explanations, reuse
reviewed checks, and avoid rerunning unchanged accepted suites. No package is
currently needed. Known E11/E13/E14 dependency findings remain dated unresolved
release/use gates, not a newly refreshed security audit. Stop and ask the owner
for instructions once Phase 5 is complete, before beginning Phase 6.
