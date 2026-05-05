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

### Open questions / TODO for next session
- Add `uv` for proper lockfile management (we deferred this)
- Write tests with `pytest` and `pytest-vcr`
- Add CLI entry point (typer)
- Add Prometheus metrics module
- Add FastAPI app with /health, /collections, /anomalies, /metrics
- Add anomaly detector
- Add Dockerfile + docker-compose
- Add GitHub Actions CI + GitLab CI mirror
- Write 3 runbooks + 3 ADRs + incident template
- Polish README with screenshots

### Application context
- Target role: VN 26/26 Junior Data Repositories Operations Engineer (Early Careers)
- Deadline: 2026-06-09
- Plan: Path A (deep learning mode), pace ~2-4 more focused sessions