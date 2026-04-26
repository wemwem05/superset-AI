# External Integrations

**Analysis Date:** 2026-03-26

## APIs & External Services

**Mapbox (Optional):**
- Mapbox Maps API - Map visualization in dashboards
  - SDK/Client: Mapbox GL JS (integrated in Superset frontend)
  - Auth: `MAPBOX_API_KEY` environment variable
  - Location: `docker/superset_config.py` line 106
  - Status: Optional - only required for map-based visualizations

## Data Storage

**Databases:**
- PostgreSQL 16 (Alpine) - Metadata database (dashboards, users, datasource definitions, query history)
  - Connection: `postgresql+psycopg2://[POSTGRES_USER]:[POSTGRES_PASSWORD]@[DATABASE_HOST]:[DATABASE_PORT]/[POSTGRES_DB]`
  - Client: psycopg2-binary (installed in `Dockerfile` line 4)
  - Environment variables:
    - `POSTGRES_USER` - Database user (default: superset)
    - `POSTGRES_PASSWORD` - Database password
    - `POSTGRES_DB` - Database name (default: superset)
    - `DATABASE_HOST` - Host address (default: postgres)
    - `DATABASE_PORT` - Port (default: 5432)
  - Volumes: `postgres_data` named volume
  - Healthcheck: `pg_isready` command, 5s interval, 5 retries
  - Located in `docker-compose.yml` lines 21-31

**File Storage:**
- Local filesystem - Superset home directory for user uploads, caches, logs
  - Volumes: `superset_home` named volume
  - Mount path: `/app/superset_home`
  - Located in `docker-compose.yml` line 9

**Caching:**
- Redis 7 (Alpine) - Multi-purpose cache and Celery message broker
  - Volumes: `redis_data` named volume
  - Healthcheck: `redis-cli ping`, 5s interval, 5 retries
  - Separate logical databases for different cache types (DB 0-5)
  - Located in `docker-compose.yml` lines 36-45

## Authentication & Identity

**Auth Provider:**
- Custom/Local - Username/password authentication via Flask-AppBuilder
  - Initial admin user created during init phase via `superset fab create-admin` command
  - Location: `docker/superset-init.sh` lines 8-13
  - Environment variables for admin user:
    - `SUPERSET_ADMIN_USERNAME` - Admin login username
    - `SUPERSET_ADMIN_FIRSTNAME` - Admin first name
    - `SUPERSET_ADMIN_LASTNAME` - Admin last name
    - `SUPERSET_ADMIN_EMAIL` - Admin email address
    - `SUPERSET_ADMIN_PASSWORD` - Admin password
  - Location: `.env.example` lines 6-12

**Extension Point:**
- Superset supports SSO integration (OAuth2/OIDC, LDAP, Google, Okta, Azure AD, Keycloak) via Flask-AppBuilder security manager
- Not currently configured in this deployment

## Monitoring & Observability

**Error Tracking:**
- Not configured - No dedicated error tracking service (Sentry, etc.)

**Logs:**
- Container stdout/stderr logs
  - Celery worker loglevel: WARNING
  - Celery beat loglevel: WARNING
  - Docker Compose log aggregation: `docker compose logs -f [service]`
  - Superset application logs: captured to container stdout

**Health Monitoring:**
- Health endpoints: Superset exposes `/health` endpoint for monitoring
- Container health checks defined:
  - PostgreSQL: `pg_isready -U ${POSTGRES_USER}`
  - Redis: `redis-cli ping`
  - Service dependencies: Health checks prevent startup until services are healthy

## CI/CD & Deployment

**Hosting:**
- Docker Compose - Local single-host deployment
- Container image: `apache/superset:4.1.1` (prebuilt official image)
- Custom image: `martian322/superset:latest` (built from `Dockerfile`)
- Location: `docker-compose.yml` line 3

**Deployment Strategy:**
- Orchestration: Docker Compose (single host)
- Service orchestration:
  - `superset-init` - One-shot init container runs migrations and setup (exits after completion)
  - `superset` - Main web service (Gunicorn)
  - `superset-worker` - Async task worker (Celery)
  - `superset-beat` - Periodic task scheduler (Celery Beat)
  - `postgres` - Metadata database
  - `redis` - Cache and message broker
- Restart policy: `unless-stopped` for all persistent services, `no` for init container
- Startup dependencies: Defined via `depends_on` with health check conditions
  - Located in `docker-compose.yml` lines 10-14, 69-75, 84-90, 100-105

**CI Pipeline:**
- Not configured in repository - No GitHub Actions, GitLab CI, or similar

## Async Task Queue

**Message Broker:**
- Redis (DB 4) - Celery broker for distributing tasks
  - Location: `docker/superset_config.py` line 70
  - URL: `redis://redis:6379/4`

**Result Backend:**
- Redis (DB 5) - Stores task execution results
  - Location: `docker/superset_config.py` line 71
  - URL: `redis://redis:6379/5`

**Scheduled Tasks:**
- Reports scheduler - Runs every 1 minute
  - Task: `reports.scheduler`
  - Located in `docker/superset_config.py` lines 77-79
- Report log pruning - Runs daily
  - Task: `reports.prune_log`
  - Located in `docker/superset_config.py` lines 81-83

**Rate Limiting:**
- SQL Lab queries: 100 requests/second
  - Task: `sql_lab.get_sql_results`
  - Located in `docker/superset_config.py` lines 73-75

**Async Operations:**
- SQL Lab query execution - Run large queries asynchronously
- Alert execution - Send alerts on schedule
- Report generation - Generate and email reports
- Imports: `superset.sql_lab`, `superset.tasks.scheduler`
  - Located in `docker/superset_config.py` line 72

## Environment Configuration

**Required env vars:**
- `SUPERSET_SECRET_KEY` - Encryption key (critical - never rotate after first deployment)
- `POSTGRES_PASSWORD` - Database password
- `SUPERSET_ADMIN_PASSWORD` - Admin user password

**Optional env vars:**
- `SUPERSET_PORT` - Web service port (default: 8088)
- `SUPERSET_LOAD_EXAMPLES` - Load example data (default: no)
- `MAPBOX_API_KEY` - Mapbox API key for map visualizations
- `REDIS_HOST` - Redis hostname (default: redis)
- `REDIS_PORT` - Redis port (default: 6379)

**Secrets location:**
- `.env` file (must be kept secret, never committed to version control)
- Template: `.env.example` - Safe template with placeholder values
- Located in `.env.example`

## Webhooks & Callbacks

**Incoming:**
- Not configured

**Outgoing:**
- Email delivery for alerts and reports (integration with mail server via Superset config)
- Requires SMTP configuration in `docker/superset_config.py` (not currently configured in this deployment)

---

*Integration audit: 2026-03-26*
