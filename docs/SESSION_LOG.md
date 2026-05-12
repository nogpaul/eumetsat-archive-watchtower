# Session log

A running record of what was built, decided, and learned in each session.
Useful for picking up tomorrow without losing context.

## Session 1 — Day 1 foundation (2026-05-05)

### Built
- Project scaffold with `src/` layout, `pyproject.toml`, `.gitignore`
- 12-factor config via `pydantic-settings` with custom validator
- Structured JSON logging via `structlog`
- EUMDAC client wrapper (`eumdac_client.py`) with lazy init, retries, structured logs
- Database models (`models.py`) with surrogate primary key + UNIQUE constraint
- Storage layer (`storage.py`) with engine caching and context-managed sessions
- Collector (`collector.py`) with idempotent inserts and per-collection error isolation

### Verified
- Authenticated against real EUMETSAT API
- Polled real products from MSG HRSEVIRI and Metop SST
- 100 products persisted in local SQLite
- Idempotency confirmed: re-running the collector skips duplicates
- Per-collection latency profiles confirmed:
  - MSG HRSEVIRI: ~30-50s (geostationary, streaming)
  - Metop SST: ~30-90 minutes (polar, ground-station dependent)

### Key decisions
- `src/` layout for proper packaging
- Adapter pattern: EUMDAC objects converted to dicts at the boundary
- 24-hour fixed lookback window (with watermark improvement noted as v0.2)
- Per-collection z-score detection (informed by the latency baseline differences above)

### Remaining work — honest scope (~12-14h Path A pacing, ~3 more sessions)

**Session 2 — application layer (~4-5h)**
- [ ] pytest setup + tests for config, eumdac_client, collector
- [ ] CLI entry point with typer (`watchtower probe`, `watchtower serve`)
- [ ] Prometheus metrics module (counters, histograms)
- [ ] FastAPI app with /health, /ready, /collections, /products, /anomalies, /metrics
- [ ] Anomaly detector with rolling-window per-collection z-score

**Session 3 — deployment + DevSecOps (~3-4h)**
- [ ] Multi-stage non-root Dockerfile with HEALTHCHECK
- [ ] docker-compose with sentinel + Prometheus + Grafana
- [ ] GitHub Actions CI (ruff, mypy, pytest, image build)
- [ ] GitLab CI mirror (.gitlab-ci.yml)
- [ ] Security workflow (Bandit, pip-audit, Trivy, CycloneDX SBOM)

**Session 4 — professional polish (~3h)**
- [ ] 3 runbooks under docs/runbooks/
- [ ] 3 ADRs under docs/adr/
- [ ] Incident template
- [ ] README with badges, architecture diagram, quickstart, screenshots
- [ ] Tag v0.1.0 and push

**Then: apply (deadline 2026-06-09)**

### Optional v0.2 ideas (post-application)
- uv for lockfile management
- Watermark-based polling (resume from last successful sensing_end)
- Bounded LLM `/explain-anomaly` endpoint with human-in-the-loop

### Application context
- Target role: VN 26/26 Junior Data Repositories Operations Engineer (Early Careers)
**Then: apply (deadline 2026-06-09)**

### Optional v0.2 ideas (post-application)
- uv for lockfile management
- Watermark-based polling (resume from last successful sensing_end)
- Bounded LLM `/explain-anomaly` endpoint with human-in-the-loop


## Session 3 — CLI (2026-05-11)

### Built
- `src/watchtower/cli.py` — typer-based CLI with three commands:
  - `watchtower probe` — runs one polling cycle (writes to DB)
  - `watchtower stats` — read-only DB summary (counts, recent products)
  - `watchtower healthcheck` — exits 0 if config/DB/EUMDAC reachable

### Verified
- All three commands run cleanly
- Real polling fetched 98 new products (96 MSG + 2 Metop)
- 197 products now in local DB
- Test suite still green (14 tests, ~1s)
- 10 commits on GitHub

### Next session — Prometheus metrics
- Counters, gauges, histograms
- `/metrics` endpoint exposing them
- Wire metrics into collector + detector

### Key vocab unlocked today
- Entry points (`[project.scripts]`)
- `typer.Option`, `typer.Exit`
- Read-only vs write commands (operational discipline)