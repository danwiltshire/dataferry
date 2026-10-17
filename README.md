# dataferry

Ferry PostgreSQL (and eventually MySQL) databases between arbitrary hosts,
without requiring direct network connectivity between the source and
destination database.

> [!WARNING]
> This is a hobby project and has not been extensively tested. The sensitive
> `/admin` endpoints currently have no authentication. Do not expose this
> service to untrusted networks or use it to manage production databases
> unless you add appropriate authentication and access controls.

[![Watch Dataferry in action](https://raw.githubusercontent.com/danwiltshire/dataferry/main/ocs/video/dataferry_readme_thumbnail.png)](https://raw.githubusercontent.com/danwiltshire/dataferry/main/docs/video/dataferry_readme_demo.mp4)

## Architecture

dataferry has two kinds of process:

- **Server** ([dataferry/server.py](dataferry/server.py)): a FastAPI
  orchestrator. It stores metadata in Postgres (agents, database connections,
  jobs), issues OAuth2 `client_credentials` tokens, and hands out dump/restore
  work to agents that ask for it.
- **Agent** ([dataferry/agent.py](dataferry/agent.py)): a plain `asyncio`
  process, not a web server. It authenticates to the orchestrator, long-polls
  for work, and runs `pg_dump`/`pg_restore` as subprocesses.

Agents are **pull-only**: they always initiate outbound connections to the
server and never accept inbound connections themselves. This means an agent
can live in a private network segment (its own VPC, on-prem network, etc.)
with access to a particular database, without that database or the agent
needing to be reachable from anywhere else.

### Data model

- `Agent`: an OAuth2 `client_credentials` identity (`client_id` +
  bcrypt-hashed `client_secret`), created via the admin API and revocable.
- `DatabaseConnection`: a source or destination database, always owned by
  exactly one `Agent` (an agent can only touch databases it's been granted).
  Credentials are resolved through an interface
  ([dataferry/credentials.py](dataferry/credentials.py)) supporting either
  hard-coded static credentials or an AWS Secrets Manager secret ARN
  (covers RDS-managed secrets for both clusters and instances).
- `Job`: a copy from one `DatabaseConnection` to another. A job moves through
  two phases, `dump` then `restore`, each leased to whichever agent owns the
  relevant connection. The dump artifact is handed off through the server
  (currently local disk, see
  [dataferry/storage.py](dataferry/storage.py)) since the two agents
  involved may not have network line-of-sight to each other.

### Job lifecycle

1. An admin creates a `Job` referencing a source and destination
   `DatabaseConnection` (`phase=dump`, `status=pending`).
2. The source connection's agent long-polls `GET /agent/jobs/next`, leases the
   job, and receives the source connection's resolved credentials.
3. The agent runs `pg_dump`, uploads the result, and reports `succeeded`. The
   server flips the job to `phase=restore`, `status=pending`, unleased.
4. The destination connection's agent (which may be the same agent, or a
   different one) leases it, downloads the artifact, runs `pg_restore`, and
   reports `succeeded`.
5. Leases expire automatically if an agent stops heartbeating, so a crashed
   agent doesn't permanently strand a job. An explicit `killed` status
   (reported on graceful shutdown) reschedules a job immediately instead of
   waiting on lease expiry.

## Project layout

```
dataferry/
  server.py       FastAPI app (mounts the routers below)
  agent.py        standalone asyncio agent process
  config.py       env-var settings (Settings, via pydantic-settings)
  db.py           async SQLAlchemy engine/session
  models.py       SQLAlchemy models (Agent, DatabaseConnection, Job)
  schemas.py      Pydantic request/response models
  auth.py         bearer-token -> Agent dependency, for agent-facing routes
  credentials.py  credential resolution (static vs AWS Secrets Manager)
  storage.py      dump artifact storage (local disk)
  routes/
    admin.py      agent/database-connection/job CRUD (no auth yet)
    oauth.py      POST /oauth/token (client_credentials grant)
    agent.py      agent-facing job polling/heartbeat/status/artifact endpoints
alembic/          database migrations
tests/            functional test suite (see below)
frontend/         React + TypeScript admin UI (see below)
```

## Running it

Requires Docker.

**1. Start Postgres, the server, and the web frontend:**

```
docker compose up -d db server frontend
```

Open `http://localhost:3000`.

**2. Create an agent.** On the "Agents & Connections" page, click
"+ NEW AGENT" and give it a name. The resulting `client_id`/`client_secret`
are shown once, use the copy buttons next to them to grab both.

**3. Start the agent**, passing those credentials via `docker compose`:

```
AGENT_CLIENT_ID=<client_id> AGENT_CLIENT_SECRET=<client_secret> docker compose up -d agent
```

**4. Seed a source database to copy** (for a quick end-to-end test, both the
source and destination connections can point at the same `db` container):

```
docker compose exec db psql -U postgres -c "CREATE DATABASE mydb;"
docker compose exec db psql -U postgres -d mydb -c \
  "CREATE TABLE widgets (id serial primary key, name text); INSERT INTO widgets (name) VALUES ('foo'), ('bar');"
```

**5. Register the source/destination `DatabaseConnection`s.** Still on
"Agents & Connections", under your agent click "+ ADD CONNECTION" twice:
once for the source (`host: db`, `database_name: mydb`, `username: postgres`,
`password: example`), once for the destination (same host/credentials, a new
`database_name` such as `mydb_2026_10_27_14_28`). It doesn't need to exist
yet, the agent creates it automatically before restoring into it.

**6. Start and watch a copy job.** On the "Copy Database" page, click
"COPY TO..." on the source connection's card, pick the destination
connection as the target template, and confirm. Progress shows on the card
itself and on the "Jobs" page (`phase` moves from `dump` to `restore`,
`status` from `pending` through `running` to `succeeded`/`failed`).

## Developing

Requires [uv](https://docs.astral.sh/uv/) in addition to Docker, to run the
server outside its container.

Install dependencies:

```
uv sync
```

Start Postgres:

```
docker compose up -d db
```

Apply migrations and run the server locally (outside Docker, against the
container's exposed port):

```
DATABASE_HOST=localhost DATABASE_PASSWORD=example uv run alembic upgrade head
DATABASE_HOST=localhost DATABASE_PASSWORD=example uv run uvicorn dataferry.server:app --reload
```

### Database migrations

After changing `dataferry/models.py`, generate and review a migration:

```
DATABASE_HOST=localhost DATABASE_PASSWORD=example uv run alembic revision --autogenerate -m "describe the change"
DATABASE_HOST=localhost DATABASE_PASSWORD=example uv run alembic upgrade head
```

### Frontend

`frontend/` is a React + TypeScript (Vite) app, styled with Tailwind (loaded
via CDN, no build step) to match a provided design. It talks to the server's
admin/oauth API directly from the browser (CORS is open on the server for
this reason), reading its base URL from `window.__ENV__.API_BASE_URL`
(`public/env.js`), which the Docker image regenerates at container start
from the `API_BASE_URL` env var so the same build works across environments.

To run it outside Docker against a locally running server:

```
cd frontend
npm install
npm run dev
```

## Tests

Tests are functional/black-box: they run the real FastAPI app in-process
(over `httpx`'s `ASGITransport`, no real sockets) against a real Postgres
database, and exercise it through the admin/oauth/agent HTTP APIs rather than
calling internal functions directly. A dedicated `pg_dump`/`pg_restore`
subprocess is faked out in the agent tests so they don't require Postgres
client tools or a second real database.

They need a reachable Postgres (the `db` service in `docker-compose.yml`
works as-is) since job-claiming uses a `SELECT ... FOR UPDATE SKIP LOCKED`
query that SQLite can't run:

```
docker compose up -d db
uv run pytest
```

A dedicated `dataferry_test` database is created automatically and its schema
is (re)created per test session; production data is never touched.
