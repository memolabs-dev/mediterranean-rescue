# Frontend architecture — Mediterranean Rescue Atlas

> Status: architecture of an independent Memo Labs prototype; neither a Data For Good nor SOS Méditerranée design decision. Frontend integration with an external partner is pending agreement on the data, scope and hosting.

## Design principles

- **React 19, TypeScript strict, TanStack Query, Base UI, MapLibre**: retain the existing stack and coherent visual system.
- **Frontend-neutral API contract**: backend-generated OpenAPI (`contracts/openapi.yaml`) supplies generated type definitions (`frontend/src/api/schema.d.ts`). Never create a second undocumented API client or duplicate server business rules.
- **Public and private boundaries**: public Explore consumes only `/api/v1/`. Volunteer workspaces use same-origin session, CSRF and `/api/private/v1/`; no cross-origin private cookies.
- **Lazy loading**: route-level `React.lazy` keeps the private bundle out of first public-page loads.
- **Domain modules**: each folder owns its screens and feature-specific helpers. Shared accessibility primitives and design tokens stay under `ui/` and `styles/`.

## Existing feature organization

```text
frontend/src/
  api/                 OpenAPI typed fetch client, CSRF middleware and schema
  explore/             Public map, timeline, events, evidence, navigation
  imports/             Private upload, diagnostics and historical imports
  ports/               Port label review, search and interpretation
  review/              Identity review and volunteers' decisions
  workspace/
    WorkspaceShell.tsx Same-origin permissions, session and navigation
    PublishWorkspace.tsx
    PublicationPrepare.tsx   First human decision (private draft)
    PublicationDecision.tsx  Second human decision (publish/withdraw)
    publicationShared.ts     Shared typed status, query key and error mapping
  ui/                  Design system primitives
  i18n/                English/French translations and formatting
  shared/              Browser behavior and geography helpers
  test/                Test fixtures
frontend/e2e/          Public and private browser journeys
```

The publication components share **only** contract types, query keys and translated errors. They do **not** cache data across the public/private boundary or change permissions locally; all mutations go through dedicated private endpoints and the Django authorization/audit domain.

## Quality gates

1. TypeScript strict / `pnpm build`, ESLint and Vitest.
2. Generated OpenAPI schema consistency against Django.
3. PostGIS migrations and contract tests (zero unexpected schema drift).
4. Production-image Playwright: map, import/review, prepare/publish/withdraw in isolated **synthetic training data**.
5. No real SOS data, secrets or invitation tokens in test artifacts.
6. Merge only with the CI fully green. Confirm the live build separately after deployment.

## Next boundaries

- Complete the independent RowReview extraction on PR #75 without touching this publication slice.
- Inspect route authorization, missing data states, abort-safe requests and mobile MapLibre marker as dedicated, test-driven follow-ups.
- When approved by the partner, connect their public frontend to the read-only OpenAPI contract; same-origin proxy for any private workflow.
