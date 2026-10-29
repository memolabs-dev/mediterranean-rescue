# Mediterranean Rescue

[![CI](https://github.com/memolabs-dev/mediterranean-rescue/actions/workflows/ci.yaml/badge.svg)](https://github.com/memolabs-dev/mediterranean-rescue/actions/workflows/ci.yaml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Rescue operations at sea, documented with their source. Mediterranean Rescue brings the public records of [SOS MEDITERRANEE](https://www.sosmediterranee.org/) together on one map: the spreadsheet behind the association's own map, and the operations its crew keeps writing in the public logbook after that spreadsheet stopped (February 2024). Volunteers check each logbook operation against its sentence before it is published, and can hand the checked rows back in the spreadsheet's own columns.

**Demo:** <https://rescue.memolabs.dev>

**New here?** Start with the [welcome guide (French)](docs/BIENVENUE.md): from cloning to your first pull request, with Docker as the only requirement.

This is an independent volunteer project, started from the [Data for Good](https://dataforgood.fr/) repository [dataforgoodfr/mediterranean-rescue](https://github.com/dataforgoodfr/mediterranean-rescue). It is not the official website of SOS MEDITERRANEE; the reference map of its operations is [map.sosmediterranee.org](https://map.sosmediterranee.org/).

## What it does

- **Public site:** a map, a feed and a month-by-month view of the published operations, each with its source and evidence; English and French.
- **Team space** (`/workspace`): a workstation for volunteers. Verify an operation against the logbook sentence it was read from, prepare and publish, match port names, follow what changed in the sources, see who decided what and why (History), practise on an invented operation first.
- **Two scheduled readers:** the Google Sheets tabs every five minutes, the public logbook every six hours. They stage rows privately; nothing is linked, drafted or published automatically ([ADR 0012](docs/decisions/0012-scheduled-sheet-reading-and-public-team-split.md), [ADR 0014](docs/decisions/0014-public-logbook-as-a-source.md)).
- **Invitations** by single-use link, roles by group, every decision recorded with its author, date and reason ([ADR 0015](docs/decisions/0015-invitations-by-single-use-link.md)).
- **Returning volunteers:** after accepting a link, an eligible volunteer may set a password on the dashboard to sign in again later; this does not provide automatic forgotten-password recovery ([ADR 0018](docs/decisions/0018-volunteer-first-login-credentials.md)).

## Stack

Django 5.2 LTS, Django REST Framework and drf-spectacular (OpenAPI contract in [`contracts/openapi.yaml`](contracts/openapi.yaml)) on PostgreSQL 17 with PostGIS. React 19 with the React Compiler, Base UI, MapLibre and TanStack Query, typed from the contract with openapi-typescript. One production image serves the API and the built frontend.

## Run it locally

Requirements: Docker with Compose, make, Python 3 (only for the script that writes `.env`).

```sh
make dev
```

Open <http://127.0.0.1:5173/> for the public site and <http://127.0.0.1:5173/workspace> for the team space, where you are signed in as `local-team`. A new `.env` starts in training mode: five fictional operations, no real data. `make help` lists the other commands.

To read the real public logbook instead, set `DATA_MODE=production` in `.env` and run `docker compose run --rm api uv run --no-sync python backend/manage.py sync_logbook`. Running the frontend on the host (`cd frontend && pnpm dev`, Node 24+ and pnpm 12.10.1) still works against the API on port 8010.

## Tests

```sh
make check
```

It runs Ruff, the backend tests on PostGIS, the migration check, and the frontend lint, type check, unit tests and build, all in Docker. CI runs the same on every pull request, plus the migration check, Django's deployment checks, the OpenAPI contract (regenerated and compared) and the production image build ([`.github/workflows/ci.yaml`](.github/workflows/ci.yaml)).

## Deploy

[`deploy/README.md`](deploy/README.md) describes the production stack: one image for the web process and the two readers, PostGIS, a TLS proxy in front. Every green commit on `main` publishes `ghcr.io/memolabs-dev/mediterranean-rescue`.

## Data and rights

- Real exports never enter the repository; tests use synthetic fixtures labelled as fictitious.
- Unknown values stay empty, never zero. No position, identity or count is invented.
- Publication needs a person with the publish role, a reason, and a source whose publication agreement is recorded. The demo publishes the spreadsheet already shown on SOS MEDITERRANEE's map, in one recorded decision ([ADR 0016](docs/decisions/0016-public-demo-and-sheet-publication.md)); logbook rows are published one by one after a check.
- The map's land outline comes from Natural Earth (public domain).

## Documentation

- [Contributing](CONTRIBUTING.md) and [security policy](SECURITY.md)
- [Project and plan](docs/PROJECT.md) (French), [architecture](docs/architecture.md), [data catalogue](docs/data-catalog.md)
- [Decision records](docs/decisions/) (French), [design system](DESIGN.md)
- [Detailed guide in French](docs/GUIDE.fr.md): imports, crosswalk, drafts, revisions, administration

## License

[MIT](LICENSE).

## Local Git hooks

Run `make hooks` once after cloning (requires `uvx` or the Python `pre-commit`
package). This installs the pre-commit entrypoint and its pinned Ruff and safety
hooks for this checkout. If a custom `core.hooksPath` already exists, the installer
preserves it instead of silently overriding your configuration.

The hook runs Ruff lint and formatting on staged Python files, checks merge
conflicts/line endings and rejects obvious private keys or oversized files.
Run `make lint` to mirror the backend's CI lint. GitHub Actions remains
responsible for the full backend, frontend, browser and container tests.
