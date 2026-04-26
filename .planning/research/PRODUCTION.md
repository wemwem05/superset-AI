# Production Hardening Research: Apache Superset 4.1.1 on Docker Compose

**Project:** Superset BI Platform (small team, single host)
**Researched:** 2026-03-26
**Overall confidence:** MEDIUM — web search tools unavailable; findings are based on
official Superset docs (version-specific knowledge), Docker/ecosystem best practices
(HIGH confidence for stable tooling like Nginx/Caddy/PostgreSQL), and training data
for Superset-specific tuning (MEDIUM confidence, flagged per topic).

---

## 1. HTTPS / TLS Termination — Nginx vs Caddy

### Recommendation: Caddy for this deployment

**Why Caddy wins for a small-team Docker Compose setup:**

- Automatic HTTPS via Let's Encrypt and ZeroSSL with zero configuration
- Single binary, single config file (`Caddyfile`) — no separate certbot cron job
- Automatic certificate renewal built in
- Reverse proxy directive is three lines vs Nginx's ~20 lines
- Docker Compose integration is straightforward using the `caddy:2-alpine` image

**Caddy Caddyfile (minimal, production-ready):**

```
your.domain.com {
    reverse_proxy superset:8088
}
```

That is the entire TLS-terminating config. Caddy handles ACME challenge, cert issuance,
HTTP→HTTPS redirect, and renewal automatically.

**Docker Compose service addition:**

```yaml
caddy:
  image: caddy:2-alpine
  restart: unless-stopped
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    - caddy_data:/data      # cert storage — must persist
    - caddy_config:/config
  depends_on:
    - superset
```

Add `caddy_data` and `caddy_config` to the `volumes:` block.

**Why not Nginx:**

Nginx requires: certbot or acme.sh installation, a cron job for renewal, separate
`nginx.conf`, and manual reload after cert renewal. It adds 3-4 moving parts that
Caddy collapses into one. For a small team deployment, the operational simplicity of
Caddy is materially lower risk.

**When Nginx makes sense instead:** If the host already runs Nginx as a system service
(not containerized), use it — don't add Caddy alongside. Also valid if the team
already has Nginx operational expertise.

**Confidence:** HIGH for the mechanical Caddy/Nginx comparison. MEDIUM for the
"Caddy automatic certs work well on your specific host" claim — DNS must resolve to
the host before first startup or ACME challenge fails.

**Critical Caddy constraint:** Automatic HTTPS requires the domain to resolve publicly
to the server's IP *before* you start the Caddy container. For internal-only deployments
(no public DNS), use a Caddyfile with a self-signed cert or a DNS-01 challenge instead:

```
your.internal.domain {
    tls internal   # self-signed, no ACME needed
    reverse_proxy superset:8088
}
```

**After adding TLS, enable in superset_config.py:**

```python
TALISMAN_ENABLED = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Strict"  # upgrade from "Lax" once on HTTPS
```

Also remove the direct port exposure from the `superset` service once Caddy is running
(or bind it to localhost only: `"127.0.0.1:8088:8088"`).

---

## 2. Secret Key Management — SUPERSET_SECRET_KEY

### The non-negotiable rule: generate once, never rotate

`SUPERSET_SECRET_KEY` is used to encrypt database connection passwords stored in
Superset's metadata database. If you rotate (change) it after dashboards and connections
exist, every saved database credential becomes unreadable and you must re-enter them all.

**Generation:**

```bash
openssl rand -base64 42
```

Produces a 56-character base64 string. 42 bytes = 336 bits of entropy, well above any
practical requirement.

**Current setup analysis:** The project reads it from `os.environ["SUPERSET_SECRET_KEY"]`
(hard failure if missing — correct) and stores it in `.env` which is gitignored. This
is acceptable for a single-host deployment. The `.env` file itself must be protected:

```bash
chmod 600 .env
```

**Escalation path if security posture increases:**

| Approach | Complexity | When to use |
|----------|------------|-------------|
| `.env` file, chmod 600 | Low | Small team, single host, current state |
| Docker Secrets | Medium | Docker Swarm only — not useful for Compose alone |
| Environment variable from shell | Low | CI/CD pipelines setting env at deploy time |
| External secrets manager (Vault, AWS SM) | High | When auditing, rotation tracking, or multi-service access required |

For the current scope (small team, single host, no compliance requirement), the `.env`
file approach is appropriate. Document clearly that `.env` must not be committed to git
(already gitignored) and must be backed up separately from the database backup.

**Confidence:** HIGH — this is well-documented Superset behavior consistent across versions.

---

## 3. Session Security — Talisman, Secure Cookies, CSRF

### Current state (already good)

The existing `superset_config.py` already sets:

```python
WTF_CSRF_ENABLED = True          # correct
SESSION_COOKIE_HTTPONLY = True   # correct
SESSION_COOKIE_SAMESITE = "Lax"  # acceptable, upgrade to "Strict" on HTTPS
TALISMAN_ENABLED = False         # intentionally off until HTTPS is ready
```

### What to enable once HTTPS is active

```python
TALISMAN_ENABLED = True
SESSION_COOKIE_SECURE = True     # cookies only sent over HTTPS
SESSION_COOKIE_SAMESITE = "Strict"
```

### What Talisman does

Flask-Talisman adds HTTP security headers automatically:

- `Strict-Transport-Security` (HSTS) — forces future connections to HTTPS
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options` — prevents clickjacking
- `Content-Security-Policy` — controls which resources can load

**Important Talisman caveat with Superset:** Superset's default Talisman config may
block certain map tiles or external resources used by geospatial charts (Mapbox). If
you enable Talisman and charts stop loading, check the browser console for CSP
violations. You may need to extend the CSP allowlist:

```python
TALISMAN_CONFIG = {
    "content_security_policy": {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:", "*.mapbox.com"],
        "connect-src": ["'self'", "*.mapbox.com"],
        "script-src": ["'self'", "'unsafe-inline'"],  # Superset requires this
        "style-src": ["'self'", "'unsafe-inline'"],
    }
}
```

**Confidence:** MEDIUM — Talisman behavior is well-documented; the CSP specifics for
Superset 4.x may differ slightly from training data. Validate in a browser after enabling.

### CSRF notes

`WTF_CSRF_ENABLED = True` is already set. No additional action needed. The CSRF token
is included automatically in all Superset forms and API calls via Flask-WTF. If you
ever integrate external tools calling the Superset API, they need to fetch and pass the
CSRF token — relevant only if the Claude dashboard import workflow uses the REST API
rather than JSON file import.

---

## 4. PostgreSQL Backup Strategy for Docker Compose

### Problem with naive backups

The simplest backup (`docker compose exec postgres pg_dump ...`) has two failure modes:
1. It is manual — someone forgets to run it
2. It runs against a live database without coordination

For Superset metadata (dashboards, datasets, chart configs, user settings, access logs),
the data is not huge but is irreplaceable. A lost week of dashboard work is a real cost.

### Recommended approach: cron-driven pg_dump to local + offsite

**Option A: Host cron job (simple, no extra containers)**

```cron
# /etc/cron.d/superset-backup — runs daily at 2am
0 2 * * * root docker compose -f /path/to/docker-compose.yml exec -T postgres \
  pg_dump -U superset superset | gzip > /backups/superset_$(date +\%F).sql.gz
```

Add a retention policy to avoid filling disk:

```cron
# Delete backups older than 30 days
30 2 * * * root find /backups -name "superset_*.sql.gz" -mtime +30 -delete
```

**Option B: Dedicated backup container (no host cron dependency)**

Add to `docker-compose.yml`:

```yaml
superset-backup:
  image: postgres:16-alpine
  env_file: .env
  volumes:
    - ./backups:/backups
    - ./docker/backup.sh:/backup.sh:ro
  entrypoint: ["crond", "-f", "-d", "8"]
  # Use a custom image with supercronic or dcron for proper cron-in-container
  depends_on:
    postgres:
      condition: service_healthy
  restart: unless-stopped
```

This approach keeps backup logic inside the Compose stack but requires a custom image
with cron. The host cron approach is simpler for a small team.

**Option C: pg_basebackup for full cluster backup (MEDIUM complexity)**

`pg_dump` produces logical backups (portable SQL). `pg_basebackup` produces physical
backups (faster to restore for large databases). For Superset metadata (typically
< 1 GB), logical `pg_dump` is the right choice — portability and simplicity outweigh
restore speed.

### Offsite storage

Local backups protect against data corruption, not against host failure. Add S3/GCS/R2
upload:

```bash
aws s3 cp /backups/superset_$(date +%F).sql.gz s3://your-bucket/superset-backups/
# or with rclone for GCS/B2/Cloudflare R2:
rclone copy /backups/ remote:your-bucket/superset-backups/
```

### What to back up

| Data | Location | Backup method |
|------|----------|---------------|
| Dashboards, charts, datasets, connections | PostgreSQL `superset` DB | pg_dump |
| Superset config | `superset_config.py` | Git (already versioned) |
| Environment variables / secrets | `.env` | Encrypted offsite (separate from code) |
| Redis data | Ephemeral cache + broker state | Not needed — Celery jobs are transient |

Redis state is intentionally not backed up. If Redis is lost, the cache is cold (queries
are slower briefly) and any in-flight async queries fail (users retry). No persistent
business data lives in Redis for this deployment.

**Confidence:** HIGH for pg_dump approach; MEDIUM for container-based cron specifics.

---

## 5. Container Resource Limits

### Why add limits

Without limits, a runaway Celery worker or slow query fan-out can starve the web
process, making the entire instance unresponsive. Limits create bulkheads.

### Recommended values for a small-team deployment (4-8 vCPU, 8-16 GB RAM host)

These are starting-point values. Adjust based on observed usage via `docker stats`.

```yaml
services:
  superset:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M

  superset-worker:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.25"
          memory: 256M

  superset-beat:
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
        reservations:
          cpus: "0.05"
          memory: 64M

  postgres:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
        reservations:
          cpus: "0.25"
          memory: 256M

  redis:
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
        reservations:
          cpus: "0.05"
          memory: 64M
```

**Syntax note:** `deploy.resources` is the Compose v3 specification and works with
`docker compose` (v2 CLI). It does NOT require Docker Swarm. The `mem_limit`/`cpus`
shorthand syntax also works but is deprecated in favor of `deploy.resources`.

**Total ceiling:** ~6 vCPU, ~6 GB RAM. Leaves headroom on an 8-vCPU/16 GB host.

**Signals to increase limits:**

- `docker stats` shows memory near limit consistently → increase worker memory
- OOMKilled events in `docker compose logs` → increase the killed container's limit
- Slow dashboard loads with worker at CPU limit → increase worker CPU or concurrency

**Confidence:** MEDIUM — values are reasonable baselines; actual usage depends heavily
on query complexity and concurrent users. Always verify with `docker stats` after
deploying with real workload.

---

## 6. Health Monitoring

### Built-in endpoint

Superset exposes `GET /health` on port 8088. It returns HTTP 200 with `"OK"` when the
web server is accepting requests. This is already the correct target for load balancer
health checks and uptime monitors.

```bash
curl -f http://localhost:8088/health
# returns: "OK"
```

### Adding healthcheck to the Superset service in Compose

The existing `docker-compose.yml` does not have a healthcheck on the `superset`
service. Adding one enables dependent-service ordering and Docker's automatic restart
logic:

```yaml
superset:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8088/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s  # gunicorn startup takes time
```

Note: `curl` is available in the `apache/superset` image. The `start_period` of 60s
prevents false-positive failures during initial startup.

### Prometheus metrics

Superset does not expose Prometheus metrics natively in 4.1.1. Options:

| Approach | Complexity | What you get |
|----------|------------|--------------|
| Caddy metrics | Low | Request rate, latency, status codes at the proxy layer |
| `statsd_exporter` sidecar | Medium | Celery task metrics via StatsD → Prometheus |
| Application-level via `prometheus_flask_exporter` | High | Full Python metrics, requires custom image |
| External uptime monitor (UptimeRobot, Better Uptime) | Very low | HTTP up/down, response time, SSL expiry |

**Recommendation for small team:** Start with an external uptime monitor (UptimeRobot
free tier covers this use case) targeting `/health`. Add Caddy's built-in metrics
endpoint if you already run Prometheus. Skip `prometheus_flask_exporter` — it requires
maintaining a custom Superset image and adds significant complexity.

**Caddy metrics (if using Caddy):**

```
{
    metrics
}

your.domain.com {
    reverse_proxy superset:8088
}
```

Exposes Prometheus metrics at `localhost:2019/metrics` on the Caddy admin interface.

### Alerting

For a small team, the highest-value alerts (ordered by effort vs impact):

1. **HTTP uptime alert** — notify when `/health` returns non-200 for > 2 minutes
   (UptimeRobot, Freshping, or similar — free tier sufficient)
2. **SSL certificate expiry alert** — warn 30 days before cert expires
   (Caddy auto-renews, but notify if renewal fails; most uptime monitors include this)
3. **Disk space** — alert when host disk > 80% (host-level monitoring via cron or
   node_exporter)
4. **Container OOM kills** — check `docker events` for oom_kill events; alert via
   a simple wrapper script or Datadog free tier

**Confidence:** HIGH for /health endpoint; MEDIUM for Prometheus integration specifics
(Superset metrics exposure may have changed in 4.x — verify against release notes).

---

## 7. Celery Worker Tuning for Small Team Usage

### Current configuration

```
--pool=prefork --concurrency=2 --max-tasks-per-child=128 -Ofair
```

This is reasonable. Analysis:

| Flag | Value | Assessment |
|------|-------|------------|
| `--pool=prefork` | prefork | Correct for CPU-bound SQL tasks |
| `--concurrency=2` | 2 | Conservative — fine for small team |
| `--max-tasks-per-child=128` | 128 | Good — recycles workers to prevent memory leaks |
| `-Ofair` | fair | Correct — prevents one slow task from blocking fast tasks |

### When to increase concurrency

Concurrency = number of simultaneous async queries the worker can execute. For a small
team (< 10 concurrent users), 2 is fine. Signs to increase:

- Users report async queries staying in "pending" state for > 30s while the worker
  is busy
- `docker compose logs superset-worker` shows a queue backlog
- `celery inspect active` shows all slots occupied

For 10-20 concurrent users, `--concurrency=4` is a reasonable next step.

### Pool type considerations

`prefork` spawns OS processes (one per concurrency slot). Each process holds a full
Python/Superset in memory. At `--concurrency=2`, this is ~400-600 MB total for the
worker service.

`gevent` (async/greenlets) uses far less memory but is only suitable for I/O-bound
tasks. SQL queries are I/O-bound at the network level but the current Superset task
stack is designed around prefork — stick with prefork unless you have memory pressure
and are willing to test.

### Beat scheduler note

The current Beat command uses `--schedule=/tmp/celerybeat-schedule`. The `/tmp`
directory is ephemeral — the schedule database is lost on container restart. This is
fine for small deployments (Beat will recreate it) but means on restart, periodic
tasks may be delayed by up to one schedule interval. For stricter scheduling
(critical report emails), move the schedule file to the persistent `superset_home`
volume:

```
--schedule=/app/superset_home/celerybeat-schedule
```

**Confidence:** MEDIUM — Celery tuning recommendations are based on general Celery
best practices and Superset community patterns. The specific memory footprint per
worker process may vary by Superset version and installed drivers.

---

## 8. Common Production Issues and How to Avoid Them

### Issue 1: SECRET_KEY rotation breaks all saved connections (CRITICAL)

**What happens:** Admin rotates the secret key (thinking it's like rotating a password).
All database connection credentials stored in Superset's metadata are encrypted with the
old key — they become unreadable. Every connection must be re-entered manually.

**Prevention:** Treat `SUPERSET_SECRET_KEY` as a one-time-set value. Document this
prominently. Generate it before first `docker compose up`, write it to `.env`, and
never change it.

**Recovery path if it happens:** Restore from a pre-rotation database backup, then
ensure the backup was made with the old key value. There is no in-place re-encryption
tool in open-source Superset (Superset Cloud has a migration tool; self-hosted does not).

---

### Issue 2: Init container re-runs and overwrites admin password

**What happens:** Admin password changes are made via the UI. Then `docker compose up`
is run again. The `superset-init` container runs `superset fab create-admin` again,
which may reset the password to the `.env` value.

**Analysis of current setup:** The init script uses `|| true`, which means if the admin
user already exists, `create-admin` will fail silently and continue. In practice,
`create-admin` with FAB does not overwrite an existing user — it returns an error that
`|| true` suppresses. This is safe, but document the behavior so the team knows not
to rely on changing admin credentials via `.env` after initial setup.

---

### Issue 3: gunicorn timeout kills long-running queries

**What happens:** User runs a slow SQL query in SQL Lab. gunicorn's `--timeout 120`
kills the worker process after 120 seconds, returning a 502 to the user.

**Current setup:** Already uses `--timeout 120` (2 minutes). For Superset, queries
should go through async execution (Celery), not synchronous gunicorn workers.

**Prevention:** Ensure `SQLLAB_ASYNC_TIME_LIMIT_SEC` is set in config (defaults to 1
hour). Educate users to use SQL Lab's "Run Async" option for long queries. The async
path uses Celery workers which have no gunicorn timeout constraint.

```python
SQLLAB_ASYNC_TIME_LIMIT_SEC = 60 * 60  # 1 hour (already the default)
```

---

### Issue 4: Docker volume data loss on `docker compose down -v`

**What happens:** Developer runs `docker compose down -v` (common when debugging).
The `-v` flag removes named volumes, wiping the PostgreSQL data and Superset home dir.

**Prevention:** Document explicitly that `docker compose down` (without `-v`) is the
safe stop command. Use `docker compose down -v` only for complete teardown.

The current `docker-compose.yml` does not show any `--volumes` in documented commands
— good. Reinforce in runbook.

---

### Issue 5: Redis memory exhaustion causes silent cache failures

**What happens:** Redis runs out of memory (no `maxmemory` set), starts refusing writes.
Superset continues serving requests but caches silently fail, causing every query to
hit the source database directly. Performance degrades; database load spikes.

**Prevention:** Set Redis memory policy:

Add to `docker-compose.yml` for the Redis service:

```yaml
redis:
  image: redis:7-alpine
  command: ["redis-server", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
```

`allkeys-lru` evicts least-recently-used keys when memory is full rather than refusing
writes. This is the correct policy for a cache-only Redis instance.

---

### Issue 6: Celery Beat duplicate scheduling on restart

**What happens:** Multiple Beat containers are run (or Beat is restarted while another
is running). Periodic tasks fire multiple times.

**Prevention:** Never scale Beat: `docker compose up --scale superset-beat=1` is the
max. The current Compose file has `container_name: superset-beat` which prevents
duplicate containers (Docker will refuse to start a second container with the same
name). This is already handled correctly.

---

### Issue 7: Missing database indexes slow Superset startup and query history

**What happens:** As the metadata DB grows (thousands of query history entries),
certain Superset pages (SQL Lab history, logs) become slow.

**Prevention:** Superset's `db upgrade` migrations handle index creation. Running
migrations via the init container on every startup (already done) keeps the schema
current. Periodically run `VACUUM ANALYZE` on the PostgreSQL metadata DB:

```bash
docker compose exec postgres psql -U superset superset -c "VACUUM ANALYZE;"
```

Add this to a weekly maintenance cron job alongside the backup.

---

### Issue 8: Superset port exposed directly to the internet

**What happens:** Port 8088 is bound on all interfaces (`0.0.0.0:8088:8088`). If the
host firewall is not configured, Superset is accessible over HTTP without TLS.

**Prevention:** Before adding a reverse proxy, restrict to localhost:

```yaml
ports:
  - "127.0.0.1:8088:8088"
```

After Caddy is running (it proxies via Docker network, not via the published port),
remove the `ports:` entry entirely from the `superset` service. Caddy reaches Superset
via the internal Docker network on port 8088 without needing the port published to
the host.

---

## Summary: Priority Action Order

For this specific deployment (small team, single host, Docker Compose, Superset 4.1.1):

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| 1 | Restrict port 8088 to localhost | 2 min | Prevents accidental HTTP exposure |
| 2 | Add Caddy reverse proxy + TLS | 30 min | Encrypts all traffic |
| 3 | Enable TALISMAN + SESSION_COOKIE_SECURE | 5 min | Locks session cookies to HTTPS |
| 4 | Set Redis maxmemory + eviction policy | 5 min | Prevents silent cache failure |
| 5 | Add pg_dump cron to host | 20 min | Daily automated backups |
| 6 | Add container resource limits | 15 min | Prevents resource starvation |
| 7 | Add /health check to superset service | 5 min | Enables Docker restart on failure |
| 8 | Set up external uptime monitor | 10 min | Alerting without Prometheus overhead |
| 9 | Move celerybeat schedule to persistent volume | 2 min | Consistent scheduling on restart |
| 10 | Document SECRET_KEY immutability | 5 min | Prevents irreversible data loss |

---

## Confidence Summary

| Topic | Confidence | Reason |
|-------|------------|--------|
| Caddy vs Nginx mechanics | HIGH | Stable, well-documented tools |
| Caddy ACME / auto-TLS | HIGH | Core Caddy feature, widely used |
| SECRET_KEY encryption behavior | HIGH | Documented Superset behavior |
| TALISMAN / session cookie settings | MEDIUM | Config keys verified from superset_config.py; CSP specifics may vary |
| PostgreSQL backup (pg_dump) | HIGH | Standard PostgreSQL tooling |
| Container resource limit syntax | HIGH | Docker Compose v3 spec |
| Resource limit values | MEDIUM | Baselines from common patterns; verify with docker stats |
| /health endpoint | HIGH | Documented Superset feature |
| Prometheus/metrics | MEDIUM | Superset 4.x metrics exposure needs verification |
| Celery tuning | MEDIUM | General Celery patterns; Superset-specific behavior may vary |
| Common pitfalls | MEDIUM-HIGH | Based on pattern analysis of the codebase + ecosystem knowledge |

---

## Gaps Requiring Validation

1. **Talisman CSP allowlist** — test in browser after enabling; Superset 4.1.1's
   built-in CSP requirements are not confirmed from official docs in this session.
   Check browser devtools console for CSP errors.

2. **SUPERSET_FEATURE_FLAGS in 4.1.1** — the current config enables
   `ENABLE_TEMPLATE_PROCESSING` which allows Jinja templating in SQL. This is a
   security surface: a compromised user account could use templates for SSRF or
   data exfiltration. Evaluate whether this feature is actively used before keeping
   it enabled.

3. **`martian322/superset:latest` image** — the Compose file uses a non-official
   Docker Hub image (`martian322/superset:latest`). The Dockerfile shows it is built
   `FROM apache/superset:4.1.1` with `psycopg2-binary` added. Verify this image is
   built from source you control (the `Dockerfile` is in the repo — good) rather than
   pulled from Docker Hub. For production, build and push to a private registry rather
   than pulling a public image.

4. **`--limit-request-line 0` gunicorn flag** — this disables the request line length
   limit. Superset likely requires this for long filter state URLs, but verify it is
   actually needed; removing it is a minor hardening improvement.
