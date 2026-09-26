# Backend microservices split — implementation plan

Spec: `docs/superpowers/specs/2026-09-26-backend-microservices-design.md` (binding authority).

Global constraints:
- Endpoint paths, schemas and status-code mappings do not change.
- Moves use `git mv` so history follows the code. Moved test assertions stay the same.
- Python deps are never installed globally or into the repo. Tests run in an ephemeral uv
  env: `PYTEST="uv run --no-project -p 3.12 --with-editable <lib> --with-requirements
  requirements.txt --with pytest --with httpx pytest -q"` from the unit's directory
  (`<lib>` = relative path to `backend/libs/kakimetch_common`).
- Every commit uses Conventional Commits.

## Task 1: Shared library `kakimetch_common`

Files: `backend/libs/kakimetch_common/{pyproject.toml, kakimetch_common/{__init__,config,database,escort_rules,excel}.py, tests/{test_config,test_escort_rules}.py}`.

1. Write `tests/test_escort_rules.py`: hard-filter issues for an unavailable day, a
   timeslot outside the appointment time, a missing wheelchair capability, a conflict,
   and a clean pass. Move `backend/tests/test_config.py` here and import from
   `kakimetch_common.config`. Run → Expected: fails with an ImportError.
2. `git mv` `app/config.py` and `app/database.py` into the package. Config loads `.env` with
   `find_dotenv(usecwd=True)`. Move `get_hard_filter_issues`, `is_available` and their
   helpers out of `matching_service` into `escort_rules.py`. Move `parse_excel_date`,
   `mobility_from_equipment`, `is_yes` and `as_text` out of `scripts/load_demo_data.py`
   into `excel.py`. The pyproject depends on psycopg2-binary and python-dotenv.
3. Run → Expected: all pass.
4. Commit `refactor(backend): extract kakimetch_common shared library`.

Test command: `cd backend/libs/kakimetch_common && uv run --no-project -p 3.12 --with-editable . --with pytest pytest -q`

## Task 2: Service directories (assessment, matching, registry, scheduling)

For each service `S`, following the spec's boundary table:

1. Write `services/S/tests/test_routes.py`, asserting that the `(method, path)` set on
   `app.main.app` is exactly S's endpoints plus `/health`. Copy `test_health.py` into it.
   `git mv` S's existing tests into it. Run → Expected: fails (no app yet).
2. `git mv` S's routes, schemas and services into `services/S/app/...`. Write `main.py`
   with CORS and only S's routers, plus `requirements.txt` and `pytest.ini`. Rewrite
   imports: `app.database`/`app.config` → `kakimetch_common.*`, the hard filter →
   `kakimetch_common.escort_rules`, `scripts.load_demo_data` helpers →
   `kakimetch_common.excel`.
3. Run → Expected: all pass.
4. Commit `refactor(backend): split <S> service`, one commit per service.

Test command: `cd backend/services/<S> && $PYTEST` (for each S)

## Task 3: Scripts and removal of the monolith

1. Write `scripts/tests/test_prepare_matching_demo.py`: posts to
   `{ASSESSMENT_API_URL}/trips/{id}/assessment` for each pending trip (HTTP mocked with
   `httpx.MockTransport`), counts accepted/rejected, and keeps going after a non-2xx
   response, reporting it as failed. `git mv tests/test_load_demo_data.py scripts/tests/`.
   Run → Expected: the new test fails.
2. Rewrite `prepare_matching_demo` to call the assessment service over httpx.
   `load_demo_data` imports from `kakimetch_common`. Delete `backend/app`, `backend/tests`,
   `backend/requirements.txt` and `backend/pytest.ini`. Add `scripts/requirements.txt`
   (openpyxl, httpx) and `backend/pytest.ini` for scripts (`pythonpath = .`,
   `testpaths = scripts/tests`).
3. Run → Expected: pass.
4. Commit `refactor(backend): point demo scripts at shared lib and assessment API`.

Test command: `cd backend && uv run --no-project -p 3.12 --with-editable libs/kakimetch_common --with-requirements scripts/requirements.txt --with pytest pytest -q`

## Task 4: Docker and local dev

1. A Dockerfile per service (as in the spec), `backend/.dockerignore`,
   `docker-compose.yml` at the root with healthchecks on 8001–8004, and Makefile targets
   `install-backend` and `dev-backend`.
2. Run `docker compose build` → Expected: all four images build. If the Docker daemon is not
   running, record that and rely on CI.
3. Commit `build(backend): add per-service Dockerfiles and compose`.

Test command: every service's `$PYTEST` again (no regressions)

## Task 5: Frontend per-service API URLs

1. Write `frontend/src/lib/api.test.ts`: stub `fetch` and assert that one function per
   service hits that service's default base URL. Run `npx vitest run src/lib/api.test.ts`
   → Expected: fails.
2. `request(service, path, init)` with the four `NEXT_PUBLIC_*_API_URL` variables, each read
   literally. Update `.env.example` and the playwright env.
3. Run vitest, typecheck and lint → Expected: pass.
4. Commit `refactor(frontend): call backend services by per-service base URL`.

Test command: `cd frontend && npx vitest run`

## Task 6: CI and docs

1. The `ci.yml` backend job becomes a matrix over the lib, the four services and scripts,
   plus a `docker` job that runs `docker compose build` with a placeholder `backend/.env`.
2. Update `backend/README.md`, `frontend/README.md`, both `.env.example` files, `CLAUDE.md`
   and the AGENTS.md §11 note.
3. Commit `ci: test and build backend services independently` and
   `docs: document microservice layout`.

Test command: all backend `$PYTEST` runs, then `cd frontend && npx vitest run`
