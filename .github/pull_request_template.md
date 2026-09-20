## Change and reason

Describe the concrete problem and resulting behavior. Link the relevant phase/decision.

## Verification

List relevant checks and their results, including any checks not run and why.

## Engineering review

- [ ] Scope and phase boundaries respected; public interfaces and documentation updated.
- [ ] Security, configuration, privacy, and data-integrity implications reviewed.
- [ ] Meaningful failure-path tests added where needed; lint, types, and relevant tests pass.
- [ ] Performance, accessibility, and operational implications considered where applicable.
- [ ] No secrets, datasets, debug artifacts, unrelated changes, or unused dependencies included.
- [ ] Remaining shortcuts have a documented mitigation and revisit/release gate.

For a data change, state source/grain/row-count effects. For a deployment or migration,
describe access controls, environment configuration, verification, and rollback/recovery.
