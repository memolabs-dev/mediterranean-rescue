# Contributing

Thanks for helping. Volunteers of any background are welcome: code, data checking, translation, design, testing on a phone.

First time here? The [welcome guide (French)](docs/BIENVENUE.md) takes you from cloning to your first pull request.

## Before you start

- Read [AGENTS.md](AGENTS.md): it holds the conventions every contributor follows, human or agent.
- For anything larger than a fix, open an issue first so we agree on the scope.
- Changes to the data model or to a contract come with a short decision record in [`docs/decisions`](docs/decisions/) (French or English).

## Conventions

- **Language.** Code, identifiers, comments, commit messages, logs and errors in English. Product text goes through the translation catalogs (`frontend/src/i18n/en.ts` is the source, `fr.ts` the French translation; French typography uses a narrow no-break space before `: ; ? !`, a test checks it).
- **Data.** Never commit real source data: exports live under `data/local/`, which Git ignores. Tests use synthetic fixtures labelled as fictitious. Unknown stays `null`, never zero.
- **Frontend.** React 19 with the React Compiler: no manual `useMemo`/`useCallback` for performance. Reads go through `api.useQuery`; never fetch inside `useEffect`. Controls come from Base UI through the wrappers of `frontend/src/ui/`.
- **API.** The OpenAPI contract is generated. After a backend change, regenerate it and the frontend types (see "Contract" below); CI fails on drift.
- **Commits.** Small, one purpose each, imperative subject line ("Add the History page", "Fix the sign-out loop").

## Workflow

1. Fork, create a branch from `main`: one branch per task.
2. Run the stack locally with `make dev` ([README](README.md#run-it-locally)).
3. Write the test first when behaviour changes; keep the suite green.
4. Run `make check`, then open a pull request against `main` and fill in the template. Keep it small: one pull request, one purpose.

`main` is protected, because every commit on it is deployed to <https://rescue.memolabs.dev>:

- nobody pushes to `main` directly, maintainers included;
- a pull request needs one approving review, resolved review threads, and the four CI checks green: *Python lint*, *Tests, contract and build*, *End-to-end on the production image*, *Production image*;
- pull requests are squash-merged and their branch is deleted.

### AI tools

Using one is optional. If you do, say so in the pull request template, review every line before pushing (you remain the author), and keep [AGENTS.md](AGENTS.md) unchanged in a task's pull request: propose changes to it in a pull request of their own.

### Contract

```sh
docker compose run --rm -T api uv run --no-sync python backend/manage.py spectacular --lang en --validate --fail-on-warn > contracts/openapi.yaml
cd frontend && pnpm codegen
```

### Checks

`make check` runs them in Docker, with Django's deployment checks and the OpenAPI contract comparison; CI adds the browser tests and the production image. The main commands, one by one:

```sh
docker compose run --rm api uv run --no-sync python backend/manage.py test catalog.tests --noinput
docker compose run --rm api uv run --no-sync python backend/manage.py makemigrations --check --dry-run
cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build
uv run ruff check backend scripts && uv run ruff format --check backend scripts
```

## Reporting a vulnerability

Please do not open a public issue; see [SECURITY.md](SECURITY.md).

## Code of conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).
