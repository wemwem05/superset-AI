# Phase 02: Reliability & Performance Tuning - Research

**Researched:** 2026-03-27
**Domain:** Docker Compose resource limits, PostgreSQL backup to S3, Docker healthchecks, Gunicorn/Celery tuning
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Backups stored in S3-compatible storage (not local volume)
- **D-02:** 7-day retention policy — daily backups, oldest auto-deleted
- **D-03:** Sidecar container with cron in docker-compose.yml — no host cron dependency
- **D-04:** Backups compressed with gzip before upload (pg_dump | gzip | s3 upload)
- **D-05:** Host machine is AWS r6a.4xlarge (16 vCPUs, 128 GB RAM) shared with Airflow
- **D-06:** Total Superset resource budget: ~25% of machine (~4 vCPUs / 32 GB RAM)
- **D-07:** Limits distributed across services to prevent any single container from starving Airflow — keeping the machine alive is the top priority
- **D-08:** Docker healthchecks only — no external monitoring stack (Prometheus/Grafana is v2 per REL-07)
- **D-09:** Superset web: curl localhost:8088/health (standard /health endpoint, no multi-check script)
- **D-10:** Worker and beat: process-level healthchecks in docker-compose.yml

### Claude's Discretion

- Performance tuning values:
  - Gunicorn worker count formula (2 * CPU + 1, tuned within the 25% budget)
  - Celery concurrency settings for small team usage
  - Cache TTL values in superset_config.py
- Exact resource limit distribution per service (within the 25% total budget)
- Backup cron schedule time (e.g., 2 AM UTC)
- S3 bucket naming and path structure
- Backup sidecar container image choice (alpine + aws-cli or similar)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REL-01 | Automated daily PostgreSQL metadata backup with retention policy | S3 sidecar backup pattern using eeshugerman/postgres-backup-s3; BACKUP_KEEP_DAYS handles retention |
| REL-02 | Container resource limits (memory, CPU) for all services | Docker Compose v2 `deploy.resources` syntax confirmed working in standalone mode |
| REL-03 | Health monitoring via Superset /health endpoint | Docker healthcheck with curl to /health; worker healthcheck with celery inspect ping |
| REL-04 | Docker Compose restart policies for all services | `restart: unless-stopped` already present on all services via x-superset-common anchor; verify backup sidecar policy |
| CFG-01 | Gunicorn workers tuned for host machine (2 * CPU + 1) | r6a.4xlarge has 16 vCPUs; formula yields 9 workers but budget-cap applies; recommend 5 within 25% budget |
| CFG-02 | Celery concurrency configured for small team usage | Increase from 2 to 4 workers; prefork pool is already correct for CPU-bound tasks |
| CFG-03 | Cache TTLs configured appropriately in superset_config.py | Current TTLs (300s general, 300s data, 600s filter/explore) are reasonable; document intentional values |
</phase_requirements>

---

## Summary

This phase adds five concrete improvements to the existing Docker Compose deployment: (1) a backup sidecar container that runs `pg_dump | gzip` on a daily cron and uploads to S3 with 7-day retention, (2) `deploy.resources` limits on all services to protect the shared host, (3) Docker healthchecks on the Superset web container (curl to `/health`) and process-level checks on worker and beat, (4) explicit confirmation that `restart: unless-stopped` is correctly applied everywhere, and (5) tuning of Gunicorn worker count and Celery concurrency in `docker-compose.yml` plus documentation of intentional cache TTLs in `superset_config.py`.

The host is an AWS r6a.4xlarge (16 vCPUs, 128 GB RAM) shared with Airflow. The Superset budget is 4 vCPUs / 32 GB RAM (25%). OOM protection is the top constraint — all memory limits must leave headroom so neither Airflow nor the OS is starved.

The existing `x-superset-common` YAML anchor in `docker-compose.yml` simplifies adding healthchecks and resource limits — both can be added to the anchor so all Superset containers inherit them, with per-service overrides where needed (init container should not share the healthcheck).

**Primary recommendation:** Use `deploy.resources.limits` under each service (Docker Compose v2 standalone mode supports this without Swarm). Use `eeshugerman/postgres-backup-s3` for the backup sidecar — it handles pg_dump, gzip, S3 upload, and retention in a minimal Alpine image with no custom scripting required.

---

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| eeshugerman/postgres-backup-s3 | latest (pinned by digest preferred) | pg_dump + gzip + S3 upload sidecar | Purpose-built for this exact use case; environment-variable driven; supports S3-compatible endpoints; `BACKUP_KEEP_DAYS` for retention |
| Docker Compose v2 | Bundled with Docker 29.x | Orchestration + resource limits | `deploy.resources` works in standalone (non-Swarm) mode in Compose v2 |
| AWS CLI v2 (inside sidecar) | Bundled in backup image | S3 upload | Standard; S3-compatible via `AWS_S3_ENDPOINT` env var for non-AWS providers |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| curl (Alpine) | Alpine built-in | Superset /health endpoint check | In Docker healthcheck for superset web container |
| celery inspect ping | Celery built-in | Worker liveness check | Healthcheck for superset-worker container |
| process file check | Shell built-in | Beat liveness check | Check that celery beat pidfile/schedule file is being updated |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| eeshugerman/postgres-backup-s3 | Custom Alpine + aws-cli script | Custom script gives more control but requires authoring, testing, and maintaining bash; pre-built image is already tested |
| eeshugerman/postgres-backup-s3 | pgbackup or WAL-G | WAL-G enables point-in-time recovery but is overkill for a metadata DB; pgbackup is less maintained |
| deploy.resources (Compose v2) | mem_limit / cpus at service level (legacy) | Legacy keys deprecated; deploy.resources is the current standard |

**Installation (sidecar image — no local install needed):**
```bash
# Image pulled automatically by docker compose up
docker pull eeshugerman/postgres-backup-s3:16
# Verify current tag for postgres:16
```

---

## Architecture Patterns

### Recommended Project Structure

No new directories required. All changes are in existing files:
```
docker-compose.yml          # add: deploy.resources, healthchecks, backup sidecar service
docker/superset_config.py   # update: document cache TTL values (no functional change needed)
.env / .env.example         # add: S3 backup credentials (S3_BUCKET, S3_ACCESS_KEY_ID, etc.)
docker/backup/              # optional: empty dir placeholder if backup scripts needed later
```

### Pattern 1: Docker Compose Resource Limits (Compose v2 standalone)

**What:** `deploy.resources.limits` enforces hard memory ceiling (OOM kill) and CPU throttle. `reservations` sets soft guarantees used by Docker scheduler.

**When to use:** All long-running services on shared hosts. Hard limits prevent OOM cascade.

**Example:**
```yaml
# Source: https://www.virtua.cloud/learn/en/tutorials/docker-compose-resource-limits-healthchecks
# Docker Compose v2 standalone (no Swarm required)
services:
  superset:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 8G
        reservations:
          cpus: '0.5'
          memory: 2G
```

### Pattern 2: Docker Healthcheck for Superset Web

**What:** Docker polls a command at `interval`; after `retries` failures the container is marked `unhealthy`. `restart: unless-stopped` does NOT auto-restart on unhealthy — only on crash. Healthcheck status is visible via `docker inspect` and `docker ps`.

**When to use:** For the web container, curl the `/health` endpoint. This is the standard Superset health endpoint (returns HTTP 200 when app is ready).

**Example:**
```yaml
# Source: Docker healthcheck docs + Superset /health endpoint
superset:
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8088/health || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
```

### Pattern 3: Celery Worker Healthcheck

**What:** `celery inspect ping` sends a ping to all workers and expects a pong response. Requires `CELERY_BROKER_URL` env var to be set so Kombu can reach Redis.

**When to use:** For superset-worker container. More reliable than checking for process existence because it validates broker connectivity too.

**Example:**
```yaml
# Source: https://github.com/apache/superset/issues/23455
superset-worker:
  healthcheck:
    test: ["CMD-SHELL", "celery --app=superset.tasks.celery_app:app inspect ping | grep -q 'pong'"]
    interval: 30s
    timeout: 30s
    retries: 3
    start_period: 60s
```

### Pattern 4: Celery Beat Healthcheck

**What:** Beat does not respond to inspect ping. Use a schedule file freshness check — Beat continuously writes to `/tmp/celerybeat-schedule`, so check if it was modified recently.

**When to use:** For superset-beat container only.

**Example:**
```yaml
# Source: Nautobot docs / celery community patterns
superset-beat:
  healthcheck:
    test: ["CMD-SHELL", "[ -f /tmp/celerybeat-schedule ] && find /tmp/celerybeat-schedule -mmin -2 | grep -q celerybeat-schedule || exit 1"]
    interval: 60s
    timeout: 10s
    retries: 3
    start_period: 60s
```

### Pattern 5: S3 Backup Sidecar

**What:** A separate container runs on a cron schedule, connects to PostgreSQL via the same Docker network, streams `pg_dump | gzip` to S3, and deletes backups older than `BACKUP_KEEP_DAYS`.

**When to use:** When the backup must run inside Docker Compose with no host cron dependency.

**Example:**
```yaml
# Source: https://github.com/eeshugerman/postgres-backup-s3
postgres-backup:
  image: eeshugerman/postgres-backup-s3:16
  environment:
    SCHEDULE: '0 2 * * *'        # 2 AM UTC daily
    BACKUP_KEEP_DAYS: 7
    S3_REGION: ${S3_REGION}
    S3_BUCKET: ${S3_BUCKET}
    S3_PREFIX: superset-backups
    S3_ACCESS_KEY_ID: ${S3_ACCESS_KEY_ID}
    S3_SECRET_ACCESS_KEY: ${S3_SECRET_ACCESS_KEY}
    # S3_ENDPOINT: ${S3_ENDPOINT}  # uncomment for non-AWS S3-compatible storage
    POSTGRES_HOST: postgres
    POSTGRES_DATABASE: ${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  depends_on:
    postgres:
      condition: service_healthy
  restart: unless-stopped
```

### Resource Budget Distribution

Host: r6a.4xlarge — 16 vCPUs, 128 GB RAM. Superset total budget: 4 vCPUs / 32 GB RAM.

Airflow is the co-tenant; OOM protection is the absolute priority. Leave at least 25% of RAM as headroom (32 GB uncommitted).

Recommended distribution within Superset's 4 vCPU / 32 GB budget:

| Service | CPU limit | Memory limit | Reservation (mem) | Rationale |
|---------|-----------|--------------|-------------------|-----------|
| superset (web) | 2.0 | 8G | 2G | Gunicorn + multiple workers; heaviest |
| superset-worker | 1.0 | 8G | 2G | SQL execution can spike; needs headroom |
| superset-beat | 0.25 | 512M | 128M | Scheduler only; very low resource use |
| postgres | 0.5 | 4G | 1G | Metadata DB; small dataset; reads only |
| redis | 0.25 | 2G | 512M | Cache + broker; all in memory |
| postgres-backup | 0.1 | 512M | 128M | Runs once per day; idle otherwise |
| **Total** | **4.1 vCPU** | **23 GB** | — | Within 32 GB budget; ~9 GB headroom |

Note: CPU limits are soft throttles, not hard reservations. Total CPU limit slightly over budget is acceptable because not all containers run at full CPU simultaneously.

### Gunicorn Worker Count

The formula from CLAUDE.md: `2 * CPU_CORES + 1`. The Superset web container gets 2 vCPUs (limit). Applying the formula: `2 * 2 + 1 = 5 workers`.

Current value in `docker-compose.yml` is `--workers 4`. Recommended: increase to `5`.

For the gunicorn command in `docker-compose.yml`:
```bash
gunicorn --bind 0.0.0.0:8088 --workers 5 --timeout 120 --limit-request-line 0 superset.app:create_app()
```

### Celery Worker Concurrency

Current: `--concurrency=2`. The worker container gets 1 vCPU. For small team usage (light async query load), `--concurrency=4` is appropriate. With `--pool=prefork`, each worker is a separate process; 4 concurrent workers on a 1-vCPU limit means they share CPU time but don't compete for memory catastrophically.

Recommended: increase from `--concurrency=2` to `--concurrency=4`.

### Cache TTL Values

Current values in `superset_config.py`:
- `CACHE_CONFIG` (general): 300s (5 min) — fine for metadata/UI state
- `DATA_CACHE_CONFIG` (query results): 300s (5 min) — for a team with regularly updating data this is appropriate; could increase to 1800s (30 min) for static datasets
- `FILTER_STATE_CACHE_CONFIG`: 600s (10 min) — session-like; good
- `EXPLORE_FORM_DATA_CACHE_CONFIG`: 600s (10 min) — temporary UI state; good

Recommendation: Increase `DATA_CACHE_CONFIG CACHE_DEFAULT_TIMEOUT` to `1800` (30 min) — queries against a PostgreSQL dataset that refreshes at most hourly benefit from longer caching. Document all TTLs with inline comments explaining the rationale.

### Anti-Patterns to Avoid

- **Using `mem_limit` / `cpus` at the top-level service key:** These are deprecated legacy syntax. Use `deploy.resources.limits` instead in Compose v2.
- **Setting memory limit without a reservation:** Leads to scheduler confusion under memory pressure. Always set both `limits` and `reservations`.
- **Using `restart: always` on the backup sidecar:** The sidecar sleeps between runs; `unless-stopped` is correct (prevents indefinite restart loops if backup fails).
- **Not setting `start_period` on healthchecks:** Superset takes 30-60 seconds to start. Without `start_period`, healthchecks fail during startup and Docker may mark the container unhealthy before it's ready.
- **Celery worker healthcheck without CELERY_BROKER_URL:** The `celery inspect ping` command requires broker connectivity. The current `docker-compose.yml` passes all env vars via `env_file: .env` — ensure `CELERY_BROKER_URL` or `REDIS_URL` is set.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| pg_dump + gzip + S3 upload + retention | Custom bash script + aws-cli Alpine | eeshugerman/postgres-backup-s3 | Handles S3 multi-part upload, gzip streaming, retention deletion, S3-compatible endpoints, and cron scheduling. Custom scripts typically miss streaming (write to disk first) and have untested retention edge cases. |
| Process-level healthcheck for Celery worker | Custom Python health file | celery inspect ping | Built-in to Celery; validates broker connectivity, not just process existence |
| Resource limit enforcement | Application-level throttling | Docker deploy.resources | Kernel-level enforcement; can't be bypassed by the application |

**Key insight:** The backup sidecar pattern is well-solved by pre-built images. Custom scripts provide no advantage and add maintenance burden for bash edge cases (S3 multi-part upload thresholds, exit code handling, cleanup on partial failures).

---

## Common Pitfalls

### Pitfall 1: deploy.resources Ignored in Old docker-compose Binary

**What goes wrong:** `deploy.resources` limits are silently ignored and containers run without limits.
**Why it happens:** The old `docker-compose` (Python v1) binary ignores the `deploy` section for non-Swarm deployments. Only the Docker CLI plugin `docker compose` (v2) honors `deploy.resources` in standalone mode.
**How to avoid:** Verify with `docker compose version` (not `docker-compose --version`). If the version is 2.x and it's the CLI plugin, `deploy.resources` works. Verify after applying limits with `docker stats`.
**Warning signs:** `docker stats` shows container memory limit as the host total RAM instead of the configured value.

### Pitfall 2: Superset Web Healthcheck start_period Too Short

**What goes wrong:** Container is marked unhealthy immediately after start, causing dependent services to fail or the container to be restarted in a loop.
**Why it happens:** Superset (Flask + Gunicorn with DB migrations check) takes 30-90 seconds to become ready. Default `start_period` is 0.
**How to avoid:** Set `start_period: 60s` for the superset web container.
**Warning signs:** `docker ps` shows `(health: starting)` for more than 60 seconds, then `(unhealthy)`.

### Pitfall 3: Celery Beat Healthcheck with inspect ping

**What goes wrong:** The `celery inspect ping` command hangs or fails for the beat container because beat is not a worker and does not respond to inspect commands.
**Why it happens:** `celery inspect ping` targets workers (consumer processes), not the scheduler.
**How to avoid:** Use the schedule file freshness check (`find /tmp/celerybeat-schedule -mmin -2`) for beat, not `inspect ping`.
**Warning signs:** Beat healthcheck always fails/times out.

### Pitfall 4: Backup Sidecar Stores Credentials in docker-compose.yml

**What goes wrong:** S3 credentials appear in version-controlled docker-compose.yml.
**Why it happens:** Using literal values instead of variable references in environment section.
**How to avoid:** Always use `${S3_ACCESS_KEY_ID}` style references in docker-compose.yml; actual values only in `.env` (gitignored).
**Warning signs:** `git diff` shows secret values in compose file.

### Pitfall 5: Memory Limit Set Without Swap Limit

**What goes wrong:** Container uses swap after hitting memory limit, degrading performance without being OOM-killed.
**Why it happens:** By default, containers can use swap equal to the memory limit. On a shared host with heavy Airflow workloads, swap contention is a real problem.
**How to avoid:** Optionally set `memswap_limit` equal to `memory` in the `deploy.resources` block to disable swap for Superset containers. This makes OOM-kill happen immediately rather than thrashing swap.
**Warning signs:** `docker stats` shows swap usage climbing on the Superset containers during heavy Airflow periods.

### Pitfall 6: Backup Container postgres Image Version Mismatch

**What goes wrong:** pg_dump version in backup container is newer than the PostgreSQL server version, causing compatibility warnings or failures.
**Why it happens:** Using a mismatched postgres client version in the backup image.
**How to avoid:** Use `eeshugerman/postgres-backup-s3:16` — the tag matches the PostgreSQL server version (postgres:16 in docker-compose.yml).
**Warning signs:** pg_dump outputs `pg_dump: warning: server version: 16.x; pg_dump version: 17.x`.

---

## Code Examples

### Resource Limits — Full Service Example
```yaml
# Source: https://www.virtua.cloud/learn/en/tutorials/docker-compose-resource-limits-healthchecks
# Apply to each service in docker-compose.yml
superset:
  <<: *superset-common
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 8G
      reservations:
        cpus: '0.5'
        memory: 2G
```

### Web Healthcheck
```yaml
# Source: Docker healthcheck docs; Superset /health endpoint returns 200 when ready
superset:
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8088/health || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
```

### Worker Healthcheck
```yaml
# Source: https://github.com/apache/superset/issues/23455
superset-worker:
  healthcheck:
    test: ["CMD-SHELL", "celery --app=superset.tasks.celery_app:app inspect ping | grep -q 'pong'"]
    interval: 30s
    timeout: 30s
    retries: 3
    start_period: 60s
```

### Beat Healthcheck
```yaml
# Source: Nautobot health-check docs; adapted for celerybeat-schedule file
superset-beat:
  healthcheck:
    test: ["CMD-SHELL", "[ -f /tmp/celerybeat-schedule ] && find /tmp/celerybeat-schedule -mmin -2 | grep -q celerybeat-schedule || exit 1"]
    interval: 60s
    timeout: 10s
    retries: 3
    start_period: 60s
```

### Backup Sidecar Service
```yaml
# Source: https://github.com/eeshugerman/postgres-backup-s3
postgres-backup:
  image: eeshugerman/postgres-backup-s3:16
  environment:
    SCHEDULE: '0 2 * * *'
    BACKUP_KEEP_DAYS: 7
    S3_REGION: ${S3_REGION}
    S3_BUCKET: ${S3_BUCKET}
    S3_PREFIX: superset-backups
    S3_ACCESS_KEY_ID: ${S3_ACCESS_KEY_ID}
    S3_SECRET_ACCESS_KEY: ${S3_SECRET_ACCESS_KEY}
    # S3_ENDPOINT: ${S3_ENDPOINT}   # for non-AWS S3-compatible providers
    POSTGRES_HOST: postgres
    POSTGRES_DATABASE: ${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  depends_on:
    postgres:
      condition: service_healthy
  restart: unless-stopped
```

### Cache TTL Documentation Block (superset_config.py)
```python
# Cache TTLs — intentional values documented here
# General Superset cache (metadata, UI state): 5 min — low-cost to recompute
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,       # 5 min
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/0",
}

# Query result cache: 30 min — PostgreSQL source data refreshes at most hourly
DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 1800,      # 30 min (was 300)
    "CACHE_KEY_PREFIX": "superset_data_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/1",
}

# Filter state: 10 min — session-like user interaction state
FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 600,       # 10 min
    "CACHE_KEY_PREFIX": "superset_filter_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/2",
}

# Explore form data: 10 min — temporary visualization builder state
EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 600,       # 10 min
    "CACHE_KEY_PREFIX": "superset_explore_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/3",
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `mem_limit: 1g` at service level | `deploy.resources.limits.memory: 1G` | Docker Compose v2 (2022+) | Old syntax deprecated; new syntax works in both standalone and Swarm |
| `docker-compose` binary (Python) | `docker compose` CLI plugin (Go) | 2022, v2 became default | deploy.resources now honored in standalone mode |
| Backup to local volume | Backup to S3 | Ongoing best practice | Offsite backup; S3 object lifecycle for retention |

**Deprecated/outdated:**
- `mem_limit` / `cpus` at top-level service (Docker Compose v2): still works but generates deprecation warnings; migrate to `deploy.resources`
- `docker-compose` v1 (Python binary): No longer distributed by Docker Desktop/CLI; Docker Compose v2 is the standard

---

## Open Questions

1. **S3 endpoint type (AWS vs S3-compatible)**
   - What we know: Decision D-01 says S3-compatible storage; decision context doesn't specify if this is AWS S3 or an alternative (e.g., Cloudflare R2, MinIO)
   - What's unclear: Whether `S3_ENDPOINT` needs to be set in `.env`
   - Recommendation: Add both `S3_ENDPOINT` commented-out line to `.env.example` and uncomment in the backup sidecar service. Implementer sets the correct value for their S3 provider.

2. **Celery worker healthcheck broker URL env var**
   - What we know: `celery inspect ping` requires broker access; current compose passes env via `env_file: .env`
   - What's unclear: Whether `.env` already has `CELERY_BROKER_URL` set, or if only `REDIS_HOST`/`REDIS_PORT` are present (superset_config.py derives the URL dynamically)
   - Recommendation: The `celery` CLI needs `CELERY_BROKER_URL` or `BROKER_URL` as a direct env var for `inspect ping` to work. Add `CELERY_BROKER_URL=redis://redis:6379/4` to `.env` (or set it in the worker service's environment block in docker-compose.yml).

3. **Backup sidecar deploy.resources**
   - What we know: Sidecar is idle 23h 58m/day; runs a single pg_dump process for a few minutes
   - What's unclear: Whether extremely low limits (e.g., 0.1 CPU) would cause backup to run too slowly for large databases
   - Recommendation: Set `memory: 512M` (pg_dump buffers in memory) and `cpus: '0.5'` (only needs CPU during the ~2 minute window). The 0.1 CPU limit in the budget table above is for idle state; throttle less aggressively during the backup window. Using the limits as stated is safe for a small metadata DB.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine | All containers | Yes | 29.2.1 | — |
| Docker Compose v2 | Resource limits, orchestration | Yes | Bundled with Docker 29.x | — |
| AWS S3 (or compatible) | REL-01 backup storage | Unknown — external service | — | User must provision; no fallback |
| AWS CLI (in sidecar) | REL-01 backup | Bundled in backup image | — | — |
| curl (in superset image) | REL-03 healthcheck | Likely bundled in Alpine image | — | Use wget as fallback |

**Missing dependencies with no fallback:**
- S3 bucket: Must be provisioned by the operator before `docker compose up`. The `.env` file must have valid S3 credentials. Plan must include a Wave 0 step to document required `.env` additions.

**Missing dependencies with fallback:**
- curl in superset container: If not present, use `wget -q --spider http://localhost:8088/health` as the healthcheck command instead.

---

## Project Constraints (from CLAUDE.md)

- **Secret key:** `SUPERSET_SECRET_KEY` generated with `openssl rand -base64 42`; never rotate after first deployment
- **HTTPS:** Session cookies and Talisman already configured via Phase 1
- **Backups:** Schedule daily `pg_dump`; store offsite (S3, GCS) — this phase implements this
- **Resource limits:** Add `mem_limit` and `cpus` to each service in `docker-compose.yml` — this phase implements this (using `deploy.resources` syntax, which is the current standard)
- **Gunicorn workers:** Tune to `2 * CPU_CORES + 1` — this phase implements this
- **Celery concurrency:** Currently 2 prefork workers; increase based on async query volume
- **Cache TTLs:** Tune `CACHE_DEFAULT_TIMEOUT` based on source data update frequency
- **Port 8088:** Already not exposed externally (Phase 1 complete); keep this constraint in place when editing docker-compose.yml

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None (infrastructure-only phase — Docker Compose YAML and Python config changes) |
| Config file | N/A |
| Quick run command | `docker compose config --quiet && echo "YAML valid"` |
| Full suite command | `docker compose up -d && docker compose ps && docker stats --no-stream` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REL-01 | Backup runs and produces valid S3 object | smoke | `docker compose logs postgres-backup \| grep -i "upload\|success"` | ❌ Wave 0 |
| REL-02 | Memory limits respected by all containers | smoke | `docker stats --no-stream --format "{{.Name}}: {{.MemUsage}}"` | N/A (manual check) |
| REL-03 | /health returns 200 | smoke | `curl -sf http://localhost:8088/health` | N/A (manual) |
| REL-04 | Restart policy is unless-stopped on all services | verification | `docker compose config \| grep -A1 restart` | N/A (manual) |
| CFG-01 | Gunicorn workers = 5 in compose command | verification | `docker compose config \| grep workers` | N/A (manual) |
| CFG-02 | Celery concurrency = 4 in compose command | verification | `docker compose config \| grep concurrency` | N/A (manual) |
| CFG-03 | Cache TTLs documented in superset_config.py | verification | `grep CACHE_DEFAULT_TIMEOUT docker/superset_config.py` | Exists (modify) |

### Sampling Rate

- **Per task commit:** `docker compose config --quiet` (validates YAML)
- **Per wave merge:** `docker compose up -d && docker ps && curl -sf http://localhost:8088/health`
- **Phase gate:** All services healthy (`docker ps` shows `(healthy)` status), backup logs show first successful run

### Wave 0 Gaps

- [ ] `.env` additions documented — S3 credential variables (`S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, optional `S3_ENDPOINT`, `CELERY_BROKER_URL`)
- [ ] `.env.example` updated with new variables and comments

*(Existing files cover all configuration changes; no new test files needed for this infrastructure-only phase)*

---

## Sources

### Primary (HIGH confidence)
- Docker Compose Deploy Specification — https://docs.docker.com/reference/compose-file/deploy/ — resource limits syntax
- virtua.cloud Docker Compose tutorial — https://www.virtua.cloud/learn/en/tutorials/docker-compose-resource-limits-healthchecks — confirmed deploy.resources works in Compose v2 standalone
- eeshugerman/postgres-backup-s3 GitHub — https://github.com/eeshugerman/postgres-backup-s3 — backup sidecar env vars and Docker Compose example
- Apache Superset GitHub issue #23455 — https://github.com/apache/superset/issues/23455 — Celery worker healthcheck command

### Secondary (MEDIUM confidence)
- celery.school Docker healthcheck guide — https://celery.school/docker-health-check-for-celery-workers — worker healthcheck patterns
- codestudy.net Docker Compose resource limits — https://www.codestudy.net/blog/how-to-specify-memory-cpu-limit-in-docker-compose-version-3/ — confirmed deploy.resources is correct for Compose v2
- Apache Superset configuration docs — https://superset.apache.org/docs/configuration/configuring-superset/ — gunicorn worker formula
- restack.io Superset Gunicorn guide — https://www.restack.io/docs/superset-knowledge-superset-gunicorn-integration — SERVER_WORKER_AMOUNT pattern

### Tertiary (LOW confidence)
- Nautobot health checks docs — https://docs.nautobot.com/projects/core/en/stable/user-guide/administration/guides/health-checks/ — beat healthcheck via file freshness (adapted pattern, not Superset-specific)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — eeshugerman/postgres-backup-s3 is purpose-built and well-documented; Docker Compose v2 resource limits verified with official docs
- Architecture: HIGH — resource budget math is straightforward given known machine specs; healthcheck patterns verified against Superset issue tracker
- Pitfalls: HIGH — deploy.resources Compose v1 issue is well-documented; other pitfalls are direct observations from existing code
- Performance tuning: MEDIUM — Gunicorn formula is standard; actual optimal values depend on production load which can only be validated at runtime

**Research date:** 2026-03-27
**Valid until:** 2026-09-27 (stable domain; Docker Compose spec and Superset config patterns change slowly)
