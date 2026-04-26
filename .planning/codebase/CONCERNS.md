# Codebase Concerns

**Analysis Date:** 2026-03-26

## Tech Debt

**Hardcoded Cache TTLs:**
- Issue: Cache timeouts are set to fixed values (300s for data, 600s for filters) with no environment-based configuration
- Files: `docker/superset_config.py` (lines 40, 48, 54, 62)
- Impact: Suboptimal performance for datasets with different freshness requirements; cannot tune without code changes
- Fix approach: Move `CACHE_DEFAULT_TIMEOUT` values to environment variables, allowing operators to tune without redeployment

**Image Build Pattern (martian322/superset:latest):**
- Issue: docker-compose.yml references custom image `martian322/superset:latest` instead of official Apache Superset image
- Files: `docker-compose.yml` (line 3)
- Impact: Builds custom Docker image every deployment; dependency on external custom image; unclear what the custom build adds
- Fix approach: Migrate to official `apache/superset:4.1.1` image; move any custom additions (psycopg2) to multi-stage build in `Dockerfile`

**TALISMAN Security Disabled by Default:**
- Issue: HTTPS security headers disabled in production config (`TALISMAN_ENABLED = False`)
- Files: `docker/superset_config.py` (line 96)
- Impact: X-Frame-Options, X-Content-Type-Options, and CSP headers not sent; vulnerable to clickjacking and MIME sniffing if not behind reverse proxy with proper headers
- Fix approach: Enable TALISMAN by default; document that it requires HTTPS reverse proxy; add comprehensive security header configuration

**Missing Rate Limiting on Web Layer:**
- Issue: Only SQL Lab queries have rate limiting (`rate_limit: "100/s"`); web API endpoints have no global rate limiting
- Files: `docker/superset_config.py` (line 74)
- Impact: Vulnerable to brute-force attacks on login, DoS on API endpoints
- Fix approach: Add Flask-Limiter integration; configure per-endpoint rate limits (login: 5/minute, dashboard queries: 100/minute)

## Security Considerations

**Secret Key Management:**
- Risk: `SUPERSET_SECRET_KEY` stored in `.env` file; no rotation mechanism documented; warning says "never rotate" but provides no vault integration
- Files: `.env.example` (line 7), `docker/superset_config.py` (line 13), `README.md` (line 167)
- Current mitigation: Documentation warns not to rotate; relies on operator discipline
- Recommendations:
  - Integrate with secrets manager (HashiCorp Vault, AWS Secrets Manager)
  - Document how to generate initial secret: `openssl rand -base64 42`
  - Add pre-startup validation that secret is not the default value
  - Consider key versioning strategy if future rotation becomes necessary

**Database Credentials in Environment:**
- Risk: PostgreSQL and Superset admin passwords passed as plaintext environment variables
- Files: `.env.example` (lines 12, 16), `docker/superset_config.py` (lines 15-18)
- Current mitigation: Compose file documents to change defaults; assumes secure `.env` file handling
- Recommendations:
  - Use Docker Secrets (if on Swarm) or Kubernetes Secrets instead of `.env`
  - Add startup check: fail if `POSTGRES_PASSWORD` or `SUPERSET_ADMIN_PASSWORD` contain default placeholder values
  - Document credential rotation procedure

**Session Cookie Security Incomplete:**
- Risk: `SESSION_COOKIE_SECURE = True` not enabled by default; relies on operator to set when HTTPS is ready
- Files: `docker/superset_config.py` (line 96, commented as "enable when behind HTTPS")
- Current mitigation: Documentation mentions it in Production Checklist
- Recommendations:
  - Auto-detect HTTPS (check reverse proxy headers: `X-Forwarded-Proto`)
  - Set `SESSION_COOKIE_SECURE = True` when `X-Forwarded-Proto: https` is detected
  - Add logging when attempting HTTPS over plain HTTP to alert operators

**Missing Authentication Integration:**
- Risk: System ships with local admin user only; no SSO/LDAP configuration provided
- Files: `docker/superset-init.sh` (lines 8-14)
- Current mitigation: README mentions need to set up OAuth/LDAP manually
- Recommendations:
  - Provide example configuration for Google OAuth, Okta, Azure AD in `superset_config.py`
  - Add environment variables for SSO configuration (CLIENT_ID, CLIENT_SECRET, etc.)
  - Document that local admin should be disabled once SSO is active

**Network Exposure Risk:**
- Risk: Redis and PostgreSQL ports not bound to localhost in Docker Compose; exposed on default Docker bridge
- Files: `docker-compose.yml` (lines 21-45)
- Current mitigation: No ports published to host; internal to Docker network only
- Recommendations:
  - Document network isolation: "Services run on internal Docker network, not accessible from host by default"
  - Add security group/firewall rules to external docs
  - Consider adding `network_mode: host` for harder isolation (with caveats)

## Performance Bottlenecks

**Celery Worker Concurrency Too Low:**
- Problem: `concurrency=2` is minimal; likely inadequate for even moderate async query volume
- Files: `docker-compose.yml` (line 83)
- Cause: Default configuration assumes small deployment; no guidance on sizing
- Improvement path:
  - Change default to `concurrency=4` for typical 4-8 CPU machine
  - Add scaling guidance: `concurrency = 2 * CPU_CORES`
  - Document monitoring query queue depth; scale workers when queue > 10

**Gunicorn Worker Count Not Tuned:**
- Problem: Fixed 4 workers; formula `2 * CPU_CORES + 1` recommends 9-17 for modern machines
- Files: `docker-compose.yml` (line 66)
- Cause: One-size-fits-all default; no automatic tuning
- Improvement path:
  - Allow `GUNICORN_WORKERS` environment variable override
  - Add startup script to auto-tune based on `nproc`
  - Document thread pool: consider `--threads=2` for I/O-bound workload (database queries)

**Redis Memory Unbounded:**
- Problem: Redis container has no memory limit; can evict cache arbitrarily
- Files: `docker-compose.yml` (line 37, no `mem_limit`)
- Cause: No resource constraints specified
- Improvement path:
  - Add `mem_limit: 512M` to Redis (typical cache size)
  - Configure Redis eviction policy: `maxmemory-policy allkeys-lru`
  - Monitor cache hit ratio; tune size based on workload

**No Query Result Caching Backend:**
- Problem: Query results cached in Redis; loses all results on Redis restart
- Files: `docker/superset_config.py` (lines 45-50)
- Cause: Redis is ephemeral, suitable for sessions but not persistent query cache
- Improvement path:
  - For production, use S3-backed results cache: `RESULTS_BACKEND = S3ResultsBackend`
  - Keep Redis for session cache, S3 for query results
  - Add lifecycle policy to S3: auto-delete results older than 7 days

## Fragile Areas

**Database Migration Dependency Chain:**
- Files: `docker-compose.yml` (lines 50-58, 70-75, 84-90), `docker/superset-init.sh` (line 5)
- Why fragile: `superset-init` must run before web/worker/beat start; if migration fails, whole system stays down
- Safe modification:
  - Never skip the `service_completed_successfully` dependency check
  - Always test migrations in staging before production
  - Keep backup database snapshot before each upgrade
  - If migration fails: restore from backup, debug locally, retry on staging
- Test coverage: No automated migration tests; rely on manual testing

**Celery Beat Schedule File in /tmp:**
- Files: `docker-compose.yml` (line 98)
- Why fragile: `/tmp` is ephemeral; schedule state lost on restart; could cause task duplication or skips
- Safe modification:
  - Move to persistent volume: `--schedule=/app/superset_home/celerybeat-schedule`
  - Or use database-backed scheduler: reconfigure with `--scheduler django_celery_beat.schedulers:DatabaseScheduler`
- Test coverage: No tests for beat scheduling; manual verification only

**Secret Key Cannot Be Rotated:**
- Files: `docker/superset_config.py` (line 13), `README.md` (line 167)
- Why fragile: Encrypted database credentials locked to initial secret; rotation breaks access
- Safe modification:
  - Document this limitation in README (currently done)
  - If rotation is needed, requires full data migration (export/reimport DB)
  - Plan for secret key as permanent per-deployment value
- Test coverage: No tests for secret key handling

**Admin User Creation Idempotent but Non-Deterministic:**
- Files: `docker/superset-init.sh` (lines 8-14)
- Why fragile: `|| true` suppresses errors; if creation fails (bad credentials), init succeeds anyway
- Safe modification:
  - Add explicit error check: fail if user creation error != "already exists"
  - Validate credentials before attempting creation
  - Document required format: minimum 8 chars, no special requirements per FAB
- Test coverage: No tests for admin user creation

## Scaling Limits

**PostgreSQL Metadata Database Capacity:**
- Current capacity: Container-based instance; limited by host disk
- Limit: ~50-100 GB of metadata reasonable; beyond that, queries slow significantly
- Scaling path:
  - Monitor table sizes: `SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables ORDER BY pg_total_relation_size DESC;`
  - At 50% capacity, migrate to managed PostgreSQL (RDS, Cloud SQL, Azure Database)
  - For HA: enable replication with read replicas for reports

**Redis Cache Capacity:**
- Current capacity: Default 512 MB (system dependent); no eviction policy configured
- Limit: When full, new cache entries silently fail; Celery tasks may queue unexpectedly
- Scaling path:
  - Monitor with `redis-cli INFO memory`
  - Add explicit `maxmemory` and `maxmemory-policy=allkeys-lru`
  - At >70% sustained usage, migrate to managed Redis (ElastiCache, Memorystore)

**Celery Task Queue Depth:**
- Current capacity: Unlimited in-memory queue; can grow unbounded during bursts
- Limit: If 2 workers fall behind, queue grows rapidly; risk of memory exhaustion
- Scaling path:
  - Monitor queue depth: `superset celery inspect active_queues`
  - Add alerting: alert if queue depth > 100 tasks
  - Scale workers: `docker compose up -d --scale superset-worker=4` (from 1)

**Gunicorn Request Queue:**
- Current capacity: Limited by worker count (4) and thread count (1 per worker)
- Limit: ~4 concurrent requests; beyond that, requests queue in OS backlog
- Scaling path:
  - Add `--threads=2` to Gunicorn (if using sync worker) for 8 concurrent
  - Scale web tier: `docker compose up -d --scale superset=2` behind load balancer
  - Add reverse proxy (Nginx) with connection buffering

## Dependencies at Risk

**Apache Superset Image Version Pinned but Upstream Updates:**
- Risk: Version 4.1.1 may accumulate security vulnerabilities; no automatic updates
- Files: `docker-compose.yml` (line 3, currently uses `martian322/superset:latest`)
- Impact: Security patches require manual intervention and testing
- Migration plan:
  - Establish update cadence: check upstream every month
  - Update to latest patch version first (e.g., 4.1.2): low risk, security-focused
  - Update to new minor (e.g., 4.2.0): medium risk, test in staging first
  - Keep upgrade history: document versions used in production

**psycopg2-binary Not Pinned:**
- Risk: Latest version pulled on each Dockerfile build; could introduce breaking changes
- Files: `Dockerfile` (line 4)
- Impact: Builds become non-deterministic; PostgreSQL connection issues possible
- Migration plan:
  - Pin to specific version: `pip install --no-cache-dir psycopg2-binary==2.9.9`
  - Or use `psycopg2` (compiled) instead of binary: more stable, requires build tools

**Redis Version 7 Minor Updates:**
- Risk: `redis:7-alpine` pulls latest 7.x; breaking changes possible in minor versions
- Files: `docker-compose.yml` (line 37)
- Impact: Cache corruption or connection issues possible
- Migration plan:
  - Pin to specific version: `redis:7.2.4-alpine`
  - Test Redis upgrade path: backup data, upgrade, verify cache functionality

**PostgreSQL 16 - Breaking Changes Risk:**
- Risk: PostgreSQL 16-alpine may receive updates; schema compatibility not guaranteed
- Files: `docker-compose.yml` (line 22)
- Impact: Database corruption possible (rare); performance changes possible
- Migration plan:
  - Document major version: "PostgreSQL 16" in README
  - Establish upgrade procedure: backup, pg_dump, major-version-upgrade, restore
  - Minor updates: automatic (safe)

## Missing Critical Features

**No Automated Backups:**
- Problem: Database backups must be manually run; no scheduled backup process documented
- Blocks: Cannot recover from accidental data loss, ransomware, or disk corruption
- Solution:
  - Add `superset-backup` service: cron-based `pg_dump` to S3/GCS daily
  - Document: `docker compose exec postgres pg_dump -U superset superset | gzip > backup_$(date +%F_%T).sql.gz`
  - Add retention policy: keep 30 days of daily backups, 12 months of weekly

**No Health Monitoring:**
- Problem: No built-in monitoring; relies on manual `docker compose logs` inspection
- Blocks: Cannot detect slow queries, task queue buildup, or resource exhaustion until user complaints
- Solution:
  - Expose Prometheus metrics: `localhost:8088/metrics` (Superset natively supports)
  - Add Prometheus + Grafana service to compose file
  - Create dashboards: worker queue depth, response times, database connections

**No Log Aggregation:**
- Problem: Logs only in stdout/stderr; lost on container restart; hard to search for errors
- Blocks: Debugging production issues requires real-time log tailing; no historical audit trail
- Solution:
  - Add ELK stack (Elasticsearch + Logstash + Kibana) or Loki
  - Configure Superset log level in `superset_config.py`: add `LOGGING_CONFIGURATOR`
  - Add structured logging: JSON format for easier parsing

**No Disaster Recovery Plan:**
- Problem: No documented RTO/RPO or recovery procedures
- Blocks: During outage, unclear how to restore service
- Solution:
  - Document: RTO = 1 hour (restore from backup, reinit containers)
  - Document: RPO = 24 hours (daily backup frequency)
  - Add runbook: "Database Corruption Recovery" with pg_restore steps
  - Test recovery quarterly: full restore to staging, verify data integrity

## Test Coverage Gaps

**Configuration Validation Untested:**
- What's not tested: Environment variable parsing, secret key validation, database URI construction
- Files: `docker/superset_config.py` (entire file), `docker/superset-init.sh` (lines 1-24)
- Risk: Typos in `.env` (e.g., `DATABASE_HOST=possgres`) cause silent failures; containers start but cannot connect
- Priority: High
- Fix approach:
  - Add `docker/validate_config.py`: test all required env vars are set and valid
  - Add startup hook: run validation before Superset starts
  - Fail loudly if `POSTGRES_PASSWORD == "CHANGE_ME"` or `SUPERSET_SECRET_KEY == "CHANGE_ME_..."`

**Migration Failure Scenarios Untested:**
- What's not tested: What happens if `superset db upgrade` fails (network issue, locked table, etc.)
- Files: `docker/superset-init.sh` (line 5)
- Risk: If migration fails silently (`set -e` catches it, but error unclear), whole startup fails mysteriously
- Priority: High
- Fix approach:
  - Add error handling: `if ! superset db upgrade; then echo "CRITICAL: DB migration failed"; exit 1; fi`
  - Add logging: capture migration output to a log file for debugging
  - Add startup probe: verify tables exist before marking container ready

**Dependency Container Health Untested:**
- What's not tested: What if Redis or PostgreSQL health check fails transiently?
- Files: `docker-compose.yml` (lines 26-30, 40-44)
- Risk: Web/worker containers may start before database is truly ready, causing connection errors
- Priority: Medium
- Fix approach:
  - Add retry logic in superset_config.py: `retry_on_startup()` for database connections
  - Increase health check retries: `retries: 10` for PostgreSQL (currently 5)
  - Add explicit startup probe: Superset waits for db connection, not just port

---

*Concerns audit: 2026-03-26*
