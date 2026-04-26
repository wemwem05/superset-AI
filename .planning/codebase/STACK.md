# Technology Stack

**Analysis Date:** 2026-03-26

## Languages

**Primary:**
- Python 3.9+ - Apache Superset application (BI platform core)

## Runtime

**Environment:**
- Docker containerized deployment
- Base image: `apache/superset:4.1.1` (official Apache Superset image)

**Package Manager:**
- pip (Python package manager)
- Lockfile: Present in Superset base image; additional packages installed at build time

## Frameworks

**Core:**
- Apache Superset 4.1.1 - Business intelligence and data visualization platform

**Web Server:**
- Gunicorn 20.1.0+ - WSGI application server
  - Configuration: 4 workers, 120s timeout, bound to `0.0.0.0:8088`
  - Located in `docker-compose.yml` line 66

**Async Task Queue:**
- Celery - Distributed task execution for async queries, alerts, and reports
  - Worker pool: prefork with 2 concurrent workers
  - Beat scheduler for periodic tasks (reports, pruning)
  - Located in `docker-compose.yml` lines 80-105

**Database ORM:**
- SQLAlchemy - Object-relational mapping for metadata database
  - Connection: PostgreSQL with psycopg2-binary driver

## Key Dependencies

**Critical:**
- psycopg2-binary - PostgreSQL database adapter
  - Installed in `Dockerfile` line 4
  - Required for metadata database connectivity

**Infrastructure:**
- Celery Config: Configured in `docker/superset_config.py` lines 69-88
  - Broker: Redis (database 4)
  - Result backend: Redis (database 5)
  - Task rate limiting: 100 requests/second for SQL lab queries
  - Beat schedule: Reports scheduler (1 min), log pruning (1 day)

## Configuration

**Environment:**
- Configuration source: `.env` file loaded by all containers
- Superset-specific configuration: `docker/superset_config.py`
- Configuration path mounted as read-only volume: `/app/superset_config.py`
- Located in `docker-compose.yml` line 8

**Key Configurations:**
- `SUPERSET_SECRET_KEY` - Encryption key for saved database credentials (critical - must be generated with `openssl rand -base64 42`)
- `SUPERSET_CONFIG_PATH` - Points to `/app/superset_config.py` (set in docker-compose.yml line 6)
- `SUPERSET_ADMIN_*` - Admin user credentials for initial setup
- `POSTGRES_*` - PostgreSQL connection parameters
- `REDIS_HOST`, `REDIS_PORT` - Redis cache and Celery broker location
- `MAPBOX_API_KEY` - Optional, for map visualization features
- `SUPERSET_LOAD_EXAMPLES` - Optional, controls example data loading

**Build:**
- Multi-stage Dockerfile with minimal custom layer
- Base: Official Apache Superset 4.1.1 image
- Custom layer: Installs psycopg2-binary for PostgreSQL support
- Located at `Dockerfile`

## Platform Requirements

**Development:**
- Docker 20.10+
- Docker Compose 1.29+
- `.env` file with required secrets

**Production:**
- Container orchestration platform (Docker Compose for single host; Kubernetes for scaling)
- PostgreSQL 16+ (or managed database service like RDS, Cloud SQL)
- Redis 7+ (or managed service like ElastiCache, Memorystore)
- Reverse proxy for HTTPS/TLS termination (Nginx, Caddy, or cloud load balancer)
- Min 2 CPU cores, 4GB RAM for single-instance deployment

## Feature Flags

**Enabled in `docker/superset_config.py`:**
- `DASHBOARD_NATIVE_FILTERS` - Native filtering in dashboards
- `DASHBOARD_CROSS_FILTERS` - Cross-filter interactions between dashboard elements
- `ENABLE_TEMPLATE_PROCESSING` - Template variable processing in SQL queries
- `ALERT_REPORTS` - Alert and report scheduling functionality

## Cache & Session Configuration

**Redis Cache Backends:**
- Default cache: Redis DB 0 (300s TTL, prefix: `superset_`)
- Data cache: Redis DB 1 (300s TTL, prefix: `superset_data_`)
- Filter state cache: Redis DB 2 (600s TTL, prefix: `superset_filter_`)
- Explore form cache: Redis DB 3 (600s TTL, prefix: `superset_explore_`)
- Celery broker: Redis DB 4
- Celery result backend: Redis DB 5

**Session Security:**
- `WTF_CSRF_ENABLED = True` - CSRF protection enabled
- `SESSION_COOKIE_HTTPONLY = True` - HttpOnly flag prevents JavaScript access
- `SESSION_COOKIE_SAMESITE = "Lax"` - Mitigates CSRF attacks
- `TALISMAN_ENABLED = False` - Should be enabled when behind HTTPS proxy

## Data Limits

**SQL Query Limits:**
- `ROW_LIMIT = 50000` - Default row limit for queries
- `SQL_MAX_ROW = 100000` - Maximum rows allowed in query results

---

*Stack analysis: 2026-03-26*
