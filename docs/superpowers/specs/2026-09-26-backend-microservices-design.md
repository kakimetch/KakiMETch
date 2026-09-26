# Backend microservices split — design

- Date: 2026-09-26
- Status: approved in conversation, pending written-spec review
- Branch: `refactor/backend-microservices` (off `dev`)

## Goal

Split the single FastAPI backend (`backend/app/`) into four independently buildable and
runnable Python services, each with its own Dockerfile, as groundwork for a later Kubernetes
deployment. Behaviour seen by the frontend and by users must not change apart from which host
each call goes to.

### Success criteria

1. Each service builds with its own Dockerfile and runs on its own.
2. `docker compose up` brings up all four services, and the existing frontend works against
   them after only the API-client base-URL change described below.
3. All existing backend tests pass, relocated to the service that owns the code.
4. CI lints, tests and builds every service and the shared library.

### Out of scope

Kubernetes manifests, image registry pushes, authentication, splitting the database,
runtime service-to-service HTTP calls, an API gateway, and any change to endpoint paths,
request/response schemas, or status-code mappings.

## Service boundaries

All services share the one Supabase Postgres database (per AGENTS.md §7: "Both read/write the
same shared data store"). No migrations are part of this change.

| Service | Host port (local) | Endpoints (paths unchanged) | Code moved from |
|---|---|---|---|
| assessment | 8001 | `GET /health`, `POST /trips/{trip_id}/assessment` | `assessment_service`, `schemas/assessment`, `routes/assessments` |
| matching | 8002 | `GET /health`, `GET /trips/{trip_id}/escort-suggestions`, `GET /trips/{trip_id}/escort-options`, `GET /matching-queue`, `PATCH /elderly-clients/{elderly_id}/matching-profile` | `matching_service`, `matching_workspace_service`, `schemas/match`, `schemas/matching_workspace`, `routes/matches`, `routes/matching_workspace` |
| registry | 8003 | `GET /health`, `GET /registry/patients`, `GET /registry/patients/{patient_id}`, `POST /registry/patients`, `PUT /registry/patients/{patient_id}`, `DELETE /registry/patients/{patient_id}`, `POST /registry/patients/{patient_id}/restore`, `POST /registry/import` | `registry_service`, `schemas/registry`, `routes/registry` |
| scheduling | 8004 | `GET /health`, `POST /trips`, `POST /trips/{trip_id}/confirm-escort`, `POST /trips/{trip_id}/cancel-assignment`, `GET /schedule` | `scheduling_service`, `trip_service`, `schemas/trip`, `routes/trips`, `routes/schedule` |

Query parameters (e.g. `?limit=3`, `?deleted=true`) are unchanged.

## Repository layout

```
backend/
  libs/kakimetch_common/
    pyproject.toml
    kakimetch_common/
      __init__.py
      config.py          # get_database_url(), get_allowed_origins() — moved from app/config.py
      database.py        # get_connection() — moved from app/database.py
      escort_rules.py    # get_hard_filter_issues, is_available, timeslot/text helpers
    tests/
  services/
    <service>/
      app/
        __init__.py
        main.py          # FastAPI app, CORS middleware, includes this service's routers
        api/routes/...   # only this service's routes (+ health)
        schemas/...      # only this service's schemas
        services/...     # only this service's logic
      tests/
      requirements.txt   # fastapi, uvicorn, psycopg2-binary (+ openpyxl, python-multipart for registry)
      pytest.ini         # pythonpath = .
      Dockerfile
  scripts/
    load_demo_data.py
    prepare_matching_demo.py
    tests/
  requirements-dev.txt   # black, pip-audit, pytest, httpx
docker-compose.yml       # repo root
```

The old `backend/app/`, `backend/tests/`, `backend/requirements.txt` and `backend/pytest.ini`
are removed once everything has moved. No parallel monolith is kept.

Each service keeps the Python package name `app`, so moved modules keep their internal imports
(`from app.schemas.match import ...`). Imports of `app.database` / `app.config` become
`kakimetch_common.database` / `kakimetch_common.config`.

## Shared library: `kakimetch_common`

- `config.py`: the same behaviour as today. It reads `DATABASE_URL` and `FRONTEND_URL` from the
  environment. For local runs outside Docker it also loads `backend/.env` when that file exists,
  found by walking up from the current working directory. Containers get their values from
  compose `env_file`/`environment`, and a missing `.env` is not an error.
- `database.py`: `get_connection()` unchanged (psycopg2, `RealDictCursor`, commit/rollback/close).
- `escort_rules.py`: the per-escort hard-filter logic used by both matching and scheduling:
  `get_hard_filter_issues`, `is_available`, and the private timeslot/text helpers they depend
  on. `rank_escorts` and `get_escort_suggestions` stay in the matching service and import from
  here. `scheduling_service` imports `get_hard_filter_issues` from here instead of from
  `matching_service`.
- The library is installed as a normal pip package: `pip install ./libs/kakimetch_common`, or
  with `-e` for local development.

## Docker

One Dockerfile per service at `backend/services/<service>/Dockerfile`, all built with
`backend/` as the build context:

```dockerfile
FROM python:3.12-slim
WORKDIR /srv
COPY libs/kakimetch_common /libs/kakimetch_common
COPY services/<service>/requirements.txt .
RUN pip install --no-cache-dir /libs/kakimetch_common -r requirements.txt
COPY services/<service>/app ./app
USER nobody
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- Every container listens on 8000 internally. Compose maps the host ports to 8001–8004 as in the table above.
- `backend/.dockerignore` excludes `.env`, `__pycache__`, `.venv`, `tests/` and `.pytest_cache`,
  so secrets and test code never enter an image.
- `docker-compose.yml` (repo root) defines the four services. Each one has
  `build: {context: ./backend, dockerfile: services/<svc>/Dockerfile}`,
  `env_file: ./backend/.env`, a port mapping, and a `healthcheck` that calls `GET /health`
  (using the Python stdlib `urllib`, since slim images have no curl).
  The frontend is not containerised in this change.

## Local development without Docker

- `make install-backend` installs `libs/kakimetch_common` in editable mode, plus every
  service's requirements and `requirements-dev.txt`, into the active Python environment.
- `make dev-backend` runs the four services with `uvicorn app.main:app --reload`, each from its
  own service directory, on ports 8001–8004.
- `make dev` still runs the frontend and backend together.

## Frontend API client

- `NEXT_PUBLIC_API_URL` is replaced by `NEXT_PUBLIC_ASSESSMENT_API_URL`,
  `NEXT_PUBLIC_MATCHING_API_URL`, `NEXT_PUBLIC_REGISTRY_API_URL` and
  `NEXT_PUBLIC_SCHEDULING_API_URL`. Their defaults are `http://localhost:8001`, `:8002`,
  `:8003` and `:8004`.
- `src/lib/api.ts`: `request<T>(path, init)` becomes `request<T>(service, path, init)`, where
  `service` is one of `"assessment" | "matching" | "registry" | "scheduling"`. Each exported
  function passes the service that owns its endpoint, following the table above. The
  exported function names, signatures and types are unchanged, so the components are untouched.
- Each `process.env.NEXT_PUBLIC_*` variable is read with a literal property name, because Next.js
  only inlines public env variables accessed that way.
- `playwright.config.ts` sets all four variables to `""`. The existing `page.route("**/…")`
  mocks keep working.
- `frontend/.env.example` lists all four variables.

## CORS

Each service's `main.py` adds the same `CORSMiddleware` configuration as today's `main.py`,
using `kakimetch_common.config.get_allowed_origins()`.

## Demo scripts

- `load_demo_data.py` imports `get_connection` from `kakimetch_common.database`. Its
  behaviour is unchanged.
- `prepare_matching_demo.py` no longer imports `assess_trip`. For each pending,
  escort-required trip it calls `POST {ASSESSMENT_API_URL}/trips/{trip_id}/assessment` over
  HTTP, where `ASSESSMENT_API_URL` defaults to `http://localhost:8001`. It uses `httpx`,
  which is already a dev dependency. A non-2xx response is reported for that trip and the
  script moves on to the rest, instead of stopping at the first failure.
- Scripts run from `backend/` as `python -m scripts.<name>`, the same as today.

## Testing

Existing tests move with their code. Their assertions stay the same, and only import paths
and monkeypatch targets change (for example `registry_service.get_connection` is now the
registry service's own module attribute).

| Current test | New location |
|---|---|
| `test_assessment_service.py` | `services/assessment/tests/` |
| `test_matching_service.py`, `test_matching_workspace_service.py`, `test_matching_workspace_schemas.py` | `services/matching/tests/` |
| `test_registry_service.py` | `services/registry/tests/` |
| `test_trip_schemas.py` | `services/scheduling/tests/` |
| `test_load_demo_data.py` | `scripts/tests/` |
| `test_config.py` | `libs/kakimetch_common/tests/` |
| `test_health.py` | one copy in each service's `tests/` |

New tests:

- `libs/kakimetch_common/tests/test_escort_rules.py`: hard-filter issues for an unavailable
  day, a timeslot outside the appointment time, a missing wheelchair capability, and a
  scheduling conflict, plus a clean pass.
- `services/<service>/tests/test_routes.py`, one per service: the set of
  `(method, path)` pairs on `app.main.app` is exactly this service's endpoints from the
  table above. This catches routes that are lost or duplicated in the split.
- `scripts/tests/test_prepare_matching_demo.py`: posts to the assessment URL for each
  pending trip (with the HTTP call mocked) and carries on after a failing response.
- `frontend/src/lib/api.test.ts`: each exported function calls the base URL of the service
  that owns its endpoint.

## CI (`.github/workflows/ci.yml`)

- The backend job becomes a matrix over `libs/kakimetch_common`, `services/assessment`,
  `services/matching`, `services/registry`, `services/scheduling` and `scripts`. Each entry
  installs the lib plus the relevant requirements and `requirements-dev.txt`, then runs
  `black --check .` and `pytest` in that directory. `pip-audit` covers every requirements file.
- A new `docker` job runs `docker compose build` with a placeholder `backend/.env`
  created in CI (containing no secrets), so a broken Dockerfile fails the build. Nothing is
  pushed.
- The frontend job is unchanged, since the env var names only matter at runtime and in the
  Playwright config.

## Documentation updates

`backend/README.md`, `frontend/README.md`, `backend/.env.example`, `frontend/.env.example`,
`Makefile` and `CLAUDE.md` are updated to the new layout, commands and ports. AGENTS.md §7 and
§11 already describe "separate services behind one backend API". The §11 diagram gets a
one-line note that the services are now separate deployables called directly by the frontend.
