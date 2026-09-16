# CommerceLens frontend

Next.js App Router, React, TypeScript, and Tailwind CSS. This is the Phase 1 foundation
page; analytics and product navigation arrive in later phases.

From the repository root:

```powershell
npm --prefix web ci
npm --prefix web run dev
```

Open <http://localhost:3000>. No frontend environment variables or API credentials are
needed yet. For checks, use `lint`, `typecheck`, and `build` in place of `dev` above.
Stop the development server before building. `start` serves a completed production build.

Read the [development walkthrough](../docs/development.md) for the complete setup and
[architecture decision](../docs/decisions/0001-foundation.md) for tooling choices.
