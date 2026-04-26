# Architecture

**Analysis Date:** 2026-03-26

## Pattern Overview

**Overall:** Docker Compose-based microservices architecture using containerized Apache Superset with distributed task processing.

**Key Characteristics:**
- Containerized multi-tier deployment (web server, async workers, scheduler)
- Orchestrated through Docker Compose for local and small-scale production deployments
- Distributed task processing using Celery with Redis message broker
- PostgreSQL as metadata store; Redis as both cache and task queue
- One-shot initialization container that runs migrations and setup before main services start

## Layers

**Web Service Layer (superset):**
- Purpose: Serves the Superset UI and handles user-facing HTTP requests
- Location: Runs from `apache/superset:4.1.1` Docker image (configured by `/Users/alimuratbekov/work/superset/Dockerfile`)
- Contains: Gunicorn application server with 4 worker processes, Flask-based web framework from Apache Superset
- Depends on: PostgreSQL (metadata DB), Redis (query result cache), initialization complete (superset-init)
- Used by: External users via HTTP port 8088

**Async Task Layer (superset-worker):**
- Purpose: Executes long-running SQL queries, generates alerts, and produces reports asynchronously
- Location: Same Superset container image, different command (`celery worker` in `/Users/alimuratbekov/work/superset/docker-compose.yml` line 83)
- Contains: Celery worker process with prefork pool, 2 concurrent workers, max 128 tasks per child
- Depends on: PostgreSQL, Redis (as broker), initialization complete
- Used by: Web service submitting async tasks; scheduled tasks from beat scheduler

**Scheduler Layer (superset-beat):**
- Purpose: Schedules periodic tasks (report generation, log pruning) on configured intervals
- Location: Same container image, Celery Beat command in docker-compose.yml line 98
- Contains: Celery Beat scheduler managing `reports.scheduler` (1-minute interval) and `reports.prune_log` (daily)
- Depends on: PostgreSQL, Redis (broker), initialization complete
- Used by: Superset worker executes scheduled tasks from beat

**Data Persistence Layer:**
- PostgreSQL (postgres service): Metadata database storing dashboards, datasets, users, connections, saved queries
- Redis (redis service): In-memory cache and Celery broker (separate Redis DBs for different purposes)

**Initialization Layer (superset-init):**
- Purpose: One-time bootstrap that runs before main services, ensuring DB is ready and admin user exists
- Location: `./docker/superset-init.sh` executed in docker-compose.yml lines 50-58
- Contains: Database migration runner (`superset db upgrade`), admin user creation, Superset initialization
- Depends on: PostgreSQL, Redis (for health checks before init)
- Used by: Block for other services (web, worker, beat) via `condition: service_completed_successfully`

## Data Flow

**Dashboard Query Execution:**

1. User clicks "Run" on a chart in the UI (web browser)
2. Web server (superset) receives HTTP request to `/superset/sql_query_exec` or similar endpoint
3. Query is parsed, validated, and either:
   - **Synchronous:** Executes immediately in web worker, returns results via Redis cache (DATA_CACHE_CONFIG)
   - **Async:** Submitted as Celery task to Redis broker (CELERY_CONFIG broker_url on Redis DB 4)
4. Celery worker picks up task, executes SQL against connected data source
5. Results stored in Redis result backend (Redis DB 5, result_backend)
6. Web UI polls or receives WebSocket notification, fetches results from Redis
7. Results cached in DATA_CACHE_CONFIG (Redis DB 1) for 300 seconds (CACHE_DEFAULT_TIMEOUT)

**Report Scheduling & Generation:**

1. Beat scheduler wakes every minute, checks beat_schedule configuration
2. `reports.scheduler` task triggers; worker picks it up
3. Worker queries database for reports configured to generate at current time
4. For each scheduled report: generates PDF/CSV from dashboard, sends via email or stores
5. `reports.prune_log` task runs daily to clean up old report generation logs

**Session & Filter State:**

1. User interacts with dashboard filters (change date range, select dimension)
2. Filter state stored temporarily in FILTER_STATE_CACHE_CONFIG (Redis DB 2, 600s TTL)
3. User navigates away and returns: filter state restored from cache
4. Explore form data (intermediate visualization state) cached in EXPLORE_FORM_DATA_CACHE_CONFIG (Redis DB 3)

**State Management:**
- Application state: PostgreSQL (persistent dashboards, datasets, users, connections)
- Query cache: Redis DB 0 (CACHE_CONFIG) — general Superset cache
- Query results cache: Redis DB 1 (DATA_CACHE_CONFIG) — SQL query results
- Filter state: Redis DB 2 (FILTER_STATE_CACHE_CONFIG) — temporary dashboard filter states
- Explore form: Redis DB 3 (EXPLORE_FORM_DATA_CACHE_CONFIG) — visualization builder state
- Celery broker: Redis DB 4 (task queue)
- Celery results: Redis DB 5 (task results)

## Key Abstractions

**Superset Configuration (superset_config.py):**
- Purpose: Centralizes all Superset settings (database, cache, Celery, security, features) via Python config
- Location: `./docker/superset_config.py` mounted read-only into containers at `/app/superset_config.py`
- Pattern: Settings instantiated from environment variables at startup; config class (CeleryConfig) for Celery setup
- Examples: SECRET_KEY derived from SUPERSET_SECRET_KEY env var; database URI built from POSTGRES_* vars; Redis configs parameterized by REDIS_HOST/REDIS_PORT

**Database URI Construction:**
- Pattern: Connection string built dynamically from environment variables (PostgreSQL user, password, host, port, DB name)
- Located in superset_config.py lines 14-19
- Allows seamless switching between containerized postgres and external managed DB (RDS, Cloud SQL)

**Redis Namespacing:**
- Pattern: Multiple Redis databases (0-5) and key prefixes used to isolate cache types and prevent collisions
- Located in superset_config.py lines 34-64
- Enables single Redis instance to serve multiple purposes without interference

**Celery Task Configuration:**
- Pattern: CeleryConfig class (lines 69-85) defines broker, result backend, imports, rate limits, and beat schedule
- Task routing via imports list (superset.sql_lab, superset.tasks.scheduler)
- Rate limiting on sql_lab.get_sql_results prevents overwhelming data sources (100 queries/second)

## Entry Points

**Web Server (superset):**
- Location: `docker-compose.yml` service definition (lines 63-75)
- Triggers: Docker container start, depends on postgres/redis health + superset-init completion
- Responsibilities: HTTP listener on 0.0.0.0:8088, routes requests to Superset Flask app via Gunicorn, serves UI, handles dashboard/chart operations

**Initialization Script (superset-init.sh):**
- Location: `./docker/superset-init.sh`
- Triggers: First container startup via `docker compose up -d`; restart policy is `no` to prevent re-running
- Responsibilities: Run DB migrations (`superset db upgrade`), create admin user if missing, call `superset init`, optionally load example data

**Celery Worker (superset-worker):**
- Location: `docker-compose.yml` service definition (lines 80-90)
- Triggers: Docker container start, depends on initialization completion
- Responsibilities: Connect to Redis broker, consume async tasks (SQL query execution), execute background work, update results in Redis backend

**Celery Beat (superset-beat):**
- Location: `docker-compose.yml` service definition (lines 95-105)
- Triggers: Docker container start, depends on initialization completion
- Responsibilities: Schedule periodic tasks according to beat_schedule (report generation every 1 minute, prune logs daily)

## Error Handling

**Strategy:** Layered error handling across container initialization, task execution, and HTTP response.

**Patterns:**
- **Init Script:** Bash `set -e` halts on first error; `||  true` suppresses expected failures (admin user already exists)
- **Database Connection:** PostgreSQL health check (pg_isready) in compose prevents services from starting before DB ready
- **Task Execution:** Celery worker logs failures to stdout (loglevel=WARNING); failed tasks stored in result backend for inspection
- **Web Request:** Gunicorn handles HTTP errors; Superset middleware catches database/cache connection failures and returns appropriate HTTP responses
- **Cache Fallback:** If Redis unavailable, Superset degrades gracefully (bypasses caching, slower but operational)

## Cross-Cutting Concerns

**Logging:**
- Web server: Gunicorn logs to stdout (visible via `docker compose logs -f superset`)
- Workers: Celery logs to stdout with configurable loglevel (currently WARNING)
- Init: Shell script echoes progress messages to stdout
- All captured by Docker and accessible via `docker compose logs`

**Validation:**
- Database connections: Test via Superset UI before saving
- SQL queries: Parsed and validated server-side before execution
- Configuration: Loaded from environment variables at startup; invalid values cause container init failure

**Authentication:**
- Local user accounts stored in PostgreSQL metadata DB (default admin user created by init script)
- Session cookies encrypted with SECRET_KEY (from environment variable)
- SESSION_COOKIE_HTTPONLY = True prevents JavaScript access; SESSION_COOKIE_SAMESITE = "Lax" mitigates CSRF
- TALISMAN_ENABLED = False (disabled until HTTPS reverse proxy in place)

---

*Architecture analysis: 2026-03-26*
