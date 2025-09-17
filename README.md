## Customer Health (FastAPI + Postgres)



One-command setup with Docker. Seeds sample data and exposes a dashboard + REST API.



### Quickstart


**Prereqs**
\- Docker Desktop (macOS/Windows/Linux)

\- Docker Compose v2 (`docker compose …`)

&nbsp; \*(If you only have the legacy plugin, use `docker-compose …` instead.)\*


### URLS 
Dashboard: http://localhost:8000/api/dashboard

API: http://localhost:8000/docs#/

### Tests

Run the tests (inside Docker):
```bash
docker compose run --rm backend pytest -q --cov=app --cov-report=term-missing -cov-fail-under=80


\*\*Run\*\*

```bash

\# from the repo root (contains docker-compose.yml)

docker compose up --build

\# or (legacy)

\# docker-compose up --build

