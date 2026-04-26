# Phase 2: Reliability & Performance Tuning - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the Superset deployment resilient with automated backups, resource limits, health monitoring, restart policies, and tuned performance settings. Covers requirements REL-01 through REL-04 and CFG-01 through CFG-03.

</domain>

<decisions>
## Implementation Decisions

### Backup Strategy
- **D-01:** Backups stored in S3-compatible storage (not local volume)
- **D-02:** 7-day retention policy — daily backups, oldest auto-deleted
- **D-03:** Sidecar container with cron in docker-compose.yml — no host cron dependency
- **D-04:** Backups compressed with gzip before upload (pg_dump | gzip | s3 upload)

### Resource Limits
- **D-05:** Host machine is AWS r6a.4xlarge (16 vCPUs, 128 GB RAM) shared with Airflow
- **D-06:** Total Superset resource budget: ~25% of machine (~4 vCPUs / 32 GB RAM)
- **D-07:** Limits distributed across services to prevent any single container from starving Airflow — keeping the machine alive is the top priority

### Health Monitoring
- **D-08:** Docker healthchecks only — no external monitoring stack (Prometheus/Grafana is v2 per REL-07)
- **D-09:** Superset web: curl localhost:8088/health (standard /health endpoint, no multi-check script)
- **D-10:** Worker and beat: process-level healthchecks in docker-compose.yml

### Claude's Discretion
- Performance tuning values (user did not select this area for discussion):
  - Gunicorn worker count formula (2 * CPU + 1, tuned within the 25% budget)
  - Celery concurrency settings for small team usage
  - Cache TTL values in superset_config.py
- Exact resource limit distribution per service (within the 25% total budget)
- Backup cron schedule time (e.g., 2 AM UTC)
- S3 bucket naming and path structure
- Backup sidecar container image choice (alpine + aws-cli or similar)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Infrastructure
- `docker-compose.yml` — Current service definitions, volumes, healthchecks, restart policies
- `docker/superset_config.py` — Superset Python config (cache TTLs, Celery config, gunicorn settings)
- `.env.example` — Environment variable reference for all services

### Requirements
- `.planning/REQUIREMENTS.md` — REL-01 through REL-04 (reliability), CFG-01 through CFG-03 (configuration)

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — Service layers, data flow, Redis DB namespacing
- `.planning/codebase/STACK.md` — Runtime specs, cache backends, Celery configuration details

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `x-superset-common` YAML anchor in docker-compose.yml — shared config for all Superset containers (env, volumes, depends_on, restart policy)
- PostgreSQL and Redis already have healthchecks defined (pg_isready, redis-cli ping)
- `restart: unless-stopped` already set on all services via the common anchor

### Established Patterns
- All Superset containers share the same base image (`martian322/superset:latest`)
- Configuration via `.env` file and `superset_config.py` mounted read-only
- Named Docker volumes for persistence (postgres_data, redis_data, superset_home)
- Service dependency chain: postgres/redis healthy → superset-init completes → web/worker/beat start

### Integration Points
- New backup sidecar container needs access to PostgreSQL (same Docker network)
- Resource limits added directly to docker-compose.yml service definitions
- Healthcheck for superset web service needs to be added (currently missing — only postgres and redis have healthchecks)
- S3 credentials will need to be added to .env

</code_context>

<specifics>
## Specific Ideas

- Machine is shared with Airflow running heavy tasks — current usage is 24% CPU / 12% memory. Superset must not starve Airflow.
- "Keeping the machine alive" is the top priority for resource limits — OOM protection is critical.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-reliability-performance*
*Context gathered: 2026-03-27*
