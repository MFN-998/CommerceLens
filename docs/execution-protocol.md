# Execution, usage, checkpointing, and recovery protocol

Permanent owner requirement, adopted **2026-09-20**, before Phase 3. Applies to every
substantial phase, task, implementation, refactor, debugging session, review, migration,
deployment, and architecture/configuration change unless the owner explicitly changes it.
It complements the [engineering standards](engineering-standards.md) and master plan.

## Plan for interruption

Treat model usage as a limited project resource. Never depend on completing a large task
in one uninterrupted session. Divide it into atomic implementation units, logical
milestones, independently verifiable steps, and recoverable Git checkpoints. A completed
milestone must be useful and understandable even if work stops immediately afterward.
Prefer implementation → validation → documentation → commit over many unfinished changes.

Before a substantial request, identify the major units and dependencies internally,
inspect the existing implementation, and choose the smallest meaningful first unit.
Checkpoint meaningful progress, not every trivial edit. When sufficient usage remains,
continue through multiple milestones rather than stopping merely because a checkpoint exists.

## Usage and reasoning effort

Check reliable exposed usage/window/reset information before a major new unit and
periodically during long work, especially at milestone boundaries. Record the consequence
for the work plan when usage constrains it. Do not invent an exact allowance, reset time,
or per-model budget if the interface does not expose one. Account-wide readings are not
a reservation for this task and can change while other tasks run.

- With ample available usage, continue normally while checkpointing milestones.
- As usage becomes limited, shrink upcoming units; finish, validate, document, and commit
  current work before starting another broad change.
- Near exhaustion, switch to preservation mode immediately; do not start cross-cutting work.
- If usage information is unavailable or ambiguous, work conservatively with frequent
  meaningful checkpoints. Never claim that an unobserved check happened.

Use deeper reasoning for architecture, security, database design, difficult debugging,
complex refactoring/performance issues, and cross-system work. Prefer an available
appropriate lower-cost mode for routine documentation, mechanical edits, and checks
when that preserves quality. Do not claim to have changed models/effort unless the
environment actually supports and confirms it. Delegate only bounded independent work
that saves time or improves quality; avoid duplicated reviews and needless parallel scope.
Usage limits never authorize weaker validation, unsafe changes, or concealed failures.
Reduce scope, not quality. Do not redeem reset credits or make purchases without the
specific user authorization required by the platform.

## Authoritative handoff: WORK_STATE.md

Maintain [WORK_STATE.md](../WORK_STATE.md) at the repository root. It is the concise,
authoritative session handoff, reconciled against actual files and Git—not a substitute
for source, tests, migrations, ADRs, or evidence. Never rely solely on conversational memory.

Keep these sections current:

1. **Project State:** phase, milestone, task, overall objective, and task/milestone status.
2. **Completed Work:** implemented functionality, fixes/refactors, and standards/remediation.
3. **Files:** created/modified/deleted/renamed files and important affected directories.
4. **Technical Decisions:** architectural, design, security, dependency, database/schema,
   and API decisions, with tradeoffs or links to their durable records.
5. **Validation:** actual tests, lint, format, types, builds, database/schema, security,
   dependency, integration/E2E, and deployment results as applicable; evidence date/scope.
6. **Current Repository Condition:** `CLEAN / STABLE`, `FUNCTIONAL WITH KNOWN ISSUES`,
   `PARTIALLY IMPLEMENTED`, or `REQUIRES IMMEDIATE FOLLOW-UP`, with an honest explanation.
7. **Incomplete Work:** failures, bugs, TODOs, deferred improvements, workarounds,
   pending migrations, blockers, and external actions needed.
8. **Exact Next Actions:** ordered, executable steps; the first must be precise enough
   to start without rereading a chat.
9. **Git State:** current branch, latest relevant/validated commit, clean/dirty observation,
   checkpoint reference, and remote/merge status where relevant.
10. **Continuation Commands:** useful startup, test, lint, build, package, database,
    migration, or Docker commands that actually apply. Never include credentials.

Update it when a milestone completes, an important decision/bug fix/migration/dependency
change occurs, direction changes, work is deferred, a checkpoint is created, or usage
availability begins constraining the session. Save an initial state before implementation;
do not wait for the entire task to finish.

State labels must be honest: `COMPLETE`, `PARTIALLY COMPLETE`, `BLOCKED`, and/or
`SAFE TO RESUME`. Use `Not yet tested` for unrun validation and record actual failures.
Distinguish historical validation from checks run this session. A known-good application
can have pending documentation changes; report Git dirtiness separately from functionality.

Avoid self-referential commit churn: record the latest known validated implementation
commit and resolve the commit containing a handoff using
`git log -1 --format="%H %s" -- WORK_STATE.md`. A file cannot contain its own future commit
hash. Clearly label a pending checkpoint, then verify Git status after committing; the
containing commit is the checkpoint. Do not invent a hash or endlessly amend it into itself.

## Git checkpoints and risk

Before significant changes inspect `git status` and relevant recent history. Preserve
pre-existing work. Use focused branches and descriptive commits that explain the actual
change; avoid meaningless checkpoint counts or messages such as "update files".
After a meaningful validated milestone, create an appropriate commit.

Before large refactors, dependency/framework upgrades, migrations, authentication or
authorization changes, API/state/configuration restructuring, security changes,
deployments, CI/CD changes, or destructive operations, establish a known-good pre-risk
checkpoint whenever practical. Record the exact restore/continuation boundary.
Git protects source/configuration; it does not roll back a database or remote deployment.
Those operations also require their own verified backup/rollback/recovery plan.

A normal safe checkpoint:

1. Finish the current atomic unit and save files.
2. Inspect `git diff` and staged changes; check for accidental corruption, secrets, and artifacts.
3. Run relevant validation and fix critical issues introduced by the unit where practical.
4. Update affected documentation and `WORK_STATE.md`, including remaining work/failures.
5. Commit the intended changes with a meaningful message.
6. Confirm `git status`, the actual commit, and any requested push; record the exact next step.

A checkpoint need not complete the larger feature. It must make the state understood
and recoverable. Incomplete work belongs on a clearly identified branch with honest
state/validation, not disguised as a completed feature or pushed into the stable baseline.
Never use destructive reset/clean/force-push as an automatic recovery step.

## Near-limit preservation procedure

In this priority order: protect repository integrity; preserve completed work; finish
the smallest active atomic operation where safe; validate important changes; record state;
create a recoverable Git checkpoint; record exact continuation; only then consider more work.

Stop expanding scope. Save files, inspect the diff, check for accidental corruption,
run the most important feasible checks, and fix immediate critical breakage if practical.
Update `WORK_STATE.md` with all unfinished work, known failures, unrun checks, external
requirements, and exact next actions. Commit appropriately and verify status. If a commit
cannot safely be made, preserve files and document the dirty paths and reason explicitly.
Never make partially implemented or broken work appear complete to fit the remaining allowance.

## Resume after interruption or a new session

After a reset, interruption, new chat/session, model change, or substantial gap, before edits:

1. Locate the actual CommerceLens repository (`D:\My Projects\CommerceLens` on this machine).
2. Read root `AGENTS.md`, the current phase's master-plan documentation, engineering standards,
   this protocol, and `WORK_STATE.md`.
3. Run `git status`; inspect recent relevant history and the handoff's checkpoint reference.
4. Inspect the named files and unresolved TODOs/issues. Compare recorded state to actual files,
   Git history, migrations, and external resources where applicable.
5. Rerun only validation needed to establish confidence; label old evidence as historical.
6. Resolve discrepancies before continuing. Preserve user changes and explain any conflict.
7. Find the first incomplete or unverified action and resume there. Do not redo correctly
   completed phases or implementations just because conversational memory is missing.

The actual repository, history, project documentation, and verified evidence take precedence
over assumptions from chat. Required knowledge must live in source, Git, this handoff,
README/guides, ADRs, examples, migration history, and tests wherever practical.

## End every substantial session deliberately

End as **COMPLETE** when the requested task/milestone is implemented, saved, appropriately
validated, documented, and checkpointed, with critical issues handled and handoff updated.
End as **SAFE TO RESUME** when the larger task is unfinished: preserve and stabilize work,
record its precise condition, validation/failures, incomplete items, checkpoint, and first
next action. A dependency may be `BLOCKED` while completed work remains `SAFE TO RESUME`.
Do not stop useful authorized work prematurely while meaningful safe progress is possible.

Introducing this protocol does not reopen Phases 1–2. Preserve their completed audited
baseline in Git, carry forward documented exceptions, initialize the handoff, and continue
Phase 3 according to the master plan and professional standards.
