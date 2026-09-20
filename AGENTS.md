# CommerceLens project instructions

On every resumed/new session, read [WORK_STATE.md](WORK_STATE.md), inspect Git status
and relevant history, reconcile recorded and actual state, and resume the first incomplete
action. Follow the permanent [execution protocol](docs/execution-protocol.md): check
available usage honestly, work in atomic verified milestones, update the handoff continuously,
and create meaningful recoverable checkpoints. End COMPLETE or SAFE TO RESUME with exact next steps.

Read [the master plan](docs/master-plan.md) and the permanent
[engineering standards](docs/engineering-standards.md) before significant work.
These standards apply to every phase, code review, architecture/deployment decision,
and handoff unless the project owner explicitly changes them.

- Preserve phase boundaries. Complete and verify the current phase before starting the next.
- Prefer small, modular, maintainable changes; do not add enterprise infrastructure without a need.
- Consider security, configuration, privacy, data integrity, tests, performance, accessibility,
  and operational consequences during implementation. Explain consequential decisions.
- Add regression tests for real failure scenarios; do not create tests that merely repeat implementation.
- Run the relevant gates in `scripts/check.ps1`; report what passed and what was not verified.
- Never commit secrets, raw/staged datasets, local environments, generated builds, or debug artifacts.
- Keep meaningful commits on focused branches. Review the diff and checks before publishing;
  do not merge or deploy without authorization. Read `CONTRIBUTING.md` for the workflow.
- Record known exceptions with severity, rationale, mitigation, and an explicit revisit gate.
  Do not claim production readiness or complete security coverage from local checks alone.
- Update affected documentation and the audit/debt record when resolving a documented limitation.

Frontend work must also follow `web/AGENTS.md` and its installed Next.js documentation.
The historical Phase 1–2 audit is in `docs/engineering-audit-phase-1-2.md`.
