# AGENTS.md

Conventions for anyone, human or agent, contributing to this repository.

## Languages
- Code, identifiers, comments, docstrings, commit messages, log and error messages: **English**, so the code can be shared with contributors from any country.
- Specifications, decision records (`docs/decisions`), project notes (`docs/`, `.agent/project`) may be written in French.
- Product language: **English by default**, with English URLs and route names. French is the first translation. Every user-facing text goes through a translation catalog; never hard-code French strings in new code.
- Existing French labels in the foundation (model choices, admin actions, current UI) are legacy; they move to translation catalogs when the React application is built.

## Frontend rules
- React 19 with the React Compiler (build-time memoization) and `eslint-plugin-react-hooks` (`pnpm lint`); do not add manual `useMemo`/`useCallback` for performance unless a measurement shows the need.
- Reads go through `api.useQuery` (TanStack Query with openapi-fetch): the AbortSignal is passed to fetch, so unobserved requests are cancelled. Never fetch inside `useEffect`.
- Requests that are not queries (uploads, reviewed decisions) use `useAbortableRequest` (`src/shared/abortable.ts`) and pass `signal` to openapi-fetch; `isAbortError` failures are not shown as errors. Only reads and searches are aborted: a write that already left is never aborted (the server may have applied it); when the screen moved on, its late result is ignored and the queries are refreshed instead. Avoid `useSuspenseQuery` where cancellation matters.
- Controls come from Base UI public exports through the thin wrappers of `src/ui/` (contracts in `docs/design/components.md`); no second control library. Animate with CSS transitions on `data-starting-style` / `data-ending-style` and motion tokens, which drop to 0 under `prefers-reduced-motion`.
- Every product string goes through `useI18n().t` with keys in `src/i18n/en.ts` (source) and `fr.ts` (type-checked translation). Dates without time are formatted in UTC; positions take their hemisphere from the sign.
- Authoritative docs: https://react.dev/llms.txt and https://base-ui.com/llms.txt (versions pinned in `frontend/package.json`).

## Data rules
- Never commit real source data. Real exports live only under `data/local/` (ignored by Git) and are never redistributed.
- Unknown stays `null`, never zero. No identity, position or count is invented. Imports create staging or drafts, never publications.
- Tests use synthetic fixtures labelled as fictitious.

## Workflow
- Read `README.md`, `docs/PROJECT.md` and the latest decision records before changing the model or a contract; record a short ADR for such changes.
- Backend tests run on PostGIS through Docker Compose (see README); the offline Sheets diagnostic tests also run on the host with `cd backend && python3 -m unittest catalog.tests.test_sheets`.
- The project is public at `memolabs-dev/mediterranean-rescue` (decision of 25 October 2026): work on a branch, run `make check`, open a small pull request against `main`. `main` is protected: one approving review and the four CI checks are required, and nobody pushes to it directly. No pull request to `dataforgoodfr/mediterranean-rescue` until Guillaume decides.
- `make dev` starts the whole stack in training mode with fictional data; never point it at real exports to "test with real data".
- Agents work one branch and one pull request at a time, and the pull request says that an AI tool was used.
- Every green commit on `main` publishes the image that https://rescue.memolabs.dev runs within minutes: `main` is production.
