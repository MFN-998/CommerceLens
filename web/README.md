# CommerceLens frontend

Next.js App Router, React, TypeScript, and Tailwind CSS. This is the application
preview. Phase 2 has prepared local data; analytics and product navigation arrive
in later phases. The preview does not fetch data or expose a database connection.

From the repository root:

```powershell
npm --prefix web ci
npm --prefix web run dev
```

Open <http://localhost:3000>. No frontend environment variables or API credentials are
needed yet. For checks, use `format:check`, `lint`, `typecheck`, and `build` in place of
`dev` above. Run `npm --prefix web run format` to apply the repository's formatting.
Stop the development server before building. `start` serves a completed production build.

## Engineering decisions

- Keep the page as a Server Component: the current content needs no client-side state,
  third-party scripts, or data requests. Introduce interactive components when a real
  product interaction needs them.
- TypeScript strict mode and the Next.js TypeScript plugin validate application code.
  `typecheck` generates route types before checking; generated Next.js files and
  incremental build caches stay out of Git.
- ESLint uses Next.js Core Web Vitals, React, accessibility, and TypeScript rules.
  A successful build does not replace a separate lint run.
- Prettier provides deterministic formatting for frontend source and configuration;
  `format:check` catches formatting drift without editing files. The ignore file
  excludes generated outputs, lockfiles, and framework-managed instruction files.
- Page language, a descriptive title, one main heading, and named landmarks support
  assistive technology. The header wraps when space is limited. The preview has no
  interactive controls, so a browser testing framework is unnecessary at this stage.

For a visible change, verify the preview at 320 CSS pixels and a desktop width,
with browser zoom increased to 200%. Check readable text, heading order, and absence
of horizontal overflow. When interactive features arrive, add keyboard and focus
checks, accessible names and error feedback, and end-to-end tests for real user flows.
Test supported browsers at the product integration stage; the current lint/build
checks do not establish full accessibility or cross-browser compliance.

## Configuration and release boundary

The development and preview servers bind to loopback. A production build is a useful
verification artifact; it is not evidence of a production deployment. Hosting,
HTTPS, security headers and content security policy, authentication where needed,
monitoring, and environment-specific deployment configuration belong to the product
integration/deployment phase and must be verified before public release.

Keep future local frontend settings in ignored `web/.env.local`, with variable names
and non-secret examples documented in a reviewed example file when they are needed.
Never put secrets in `NEXT_PUBLIC_*` variables: Next.js embeds these values into
browser bundles at build time. Server credentials must stay in server-only code and
must never be serialized into page props. The preview's `noindex` metadata asks search
engines not to index it; it is not an access-control mechanism.

The root `.gitignore` excludes generated output and local environment files. Keep
dependency changes explicit, preserve `package-lock.json`, and verify with `npm ci`.
Do not force incompatible peer dependency upgrades to silence an audit warning.

Read the [development walkthrough](../docs/development.md) for the complete setup and
[architecture decision](../docs/decisions/0001-foundation.md) for tooling choices.
