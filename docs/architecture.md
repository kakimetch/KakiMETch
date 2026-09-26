# KakiMETch architecture

Current state of the system. Product scope and business rules are in [AGENTS.md](../AGENTS.md).

## Components

```mermaid
flowchart LR
    admin(["Admin (Rose)<br/>browser"])

    subgraph FE["frontend/ — Next.js 16"]
        landing["/ landing page"]
        registry_ui["/app/registry<br/>patient registry"]
        matching_ui["/app/matching<br/>matching workspace + schedule"]
        api_ts["src/lib/api.ts<br/>request(service, path)"]
    end

    subgraph BE["backend/services — FastAPI, one Docker image each"]
        assessment["assessment :8001<br/>POST /trips/{id}/assessment"]
        matching["matching :8002<br/>escort-suggestions · escort-options<br/>matching-queue · matching-profile"]
        registry["registry :8003<br/>/registry/patients CRUD · restore<br/>/registry/import (.xlsx)"]
        scheduling["scheduling :8004<br/>POST /trips · confirm-escort<br/>cancel-assignment · /schedule"]
    end

    common[["backend/libs/kakimetch_common<br/>web.create_app · config · database<br/>escort_rules · excel"]]

    subgraph DB["Supabase Postgres — supabase/migrations"]
        clients[(elderly_clients)]
        escorts[(escorts)]
        trips[(trips)]
    end

    scripts["backend/scripts<br/>load_demo_data · prepare_matching_demo"]
    data[/"data/*.xlsx<br/>dummy LH workbooks"/]

    admin --> landing & registry_ui & matching_ui
    registry_ui & matching_ui --> api_ts
    api_ts -->|NEXT_PUBLIC_ASSESSMENT_API_URL| assessment
    api_ts -->|NEXT_PUBLIC_MATCHING_API_URL| matching
    api_ts -->|NEXT_PUBLIC_REGISTRY_API_URL| registry
    api_ts -->|NEXT_PUBLIC_SCHEDULING_API_URL| scheduling

    assessment & matching & registry & scheduling -.->|imports| common
    common -->|psycopg2, direct SQL| DB

    data --> scripts
    scripts -->|clients: POST /registry/import| registry
    scripts -->|pending trips: POST .../assessment| assessment
    scripts -->|escorts + trips: direct SQL| DB
```

- Services never import each other; shared code lives only in `kakimetch_common`.
- All four services share one database (no per-service schemas).
- The frontend does not talk to Supabase directly.
- Matching and scheduling both apply the escort hard filters from
  `kakimetch_common.escort_rules` (`load_escorts_for_slot` + `get_hard_filter_issues`), so
  suggestions and the final confirm check can never disagree.

## Trip lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: scheduling POST /trips
    pending --> rejected: assessment fails a hard check
    pending --> accepted: assessment passes
    accepted --> scheduled: admin confirms escort (scheduling)
    scheduled --> accepted: cancel assignment (scheduling)
    rejected --> [*]
```

Matching (suggestions, roster) is only allowed on `accepted` or `scheduled` trips. Confirming an
escort who fails a hard filter needs `assignment_override` plus a written reason.

## Running it

| Where | How |
|---|---|
| Docker | `docker compose up --build` (repo root; needs `backend/.env`) |
| Local | `make install-backend && make dev` |
| Database | apply `supabase/migrations/*.sql` in filename order |
| Demo data | `cd backend && python -m scripts.load_demo_data`, then `python -m scripts.prepare_matching_demo` |
