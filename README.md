# Apache Superset — Production Deployment

Self-hosted Apache Superset for company BI, running on Docker Compose with PostgreSQL, Redis, and Celery workers.

## Architecture

| Service | Purpose |
|---|---|
| **superset** | Gunicorn web server (4 workers) |
| **superset-worker** | Celery worker for async SQL queries, alerts & reports |
| **superset-beat** | Celery Beat scheduler for periodic tasks |
| **superset-init** | One-shot container: runs DB migrations and creates admin user |
| **postgres** | Metadata database (PostgreSQL 16) |
| **redis** | Cache + Celery message broker |

## Prerequisites

- Docker Engine 20.10+
- Docker Compose v2

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and **change at minimum**:

| Variable | What to set |
|---|---|
| `SUPERSET_SECRET_KEY` | A long random string (e.g. `openssl rand -base64 42`) |
| `SUPERSET_ADMIN_PASSWORD` | A strong admin password |
| `POSTGRES_PASSWORD` | A strong database password |

### 2. Start all services

```bash
docker compose up -d
```

The first run will:
1. Pull images
2. Start PostgreSQL and Redis
3. Run database migrations and create the admin user (`superset-init`)
4. Start the web server, Celery worker, and Beat scheduler

### 3. Open Superset

Navigate to **http://localhost:8088** (or the port you set in `.env`).

Log in with the credentials from your `.env` file (default: `admin` / `admin`).

## Connecting Your Data Sources

This is the core step for building dashboards on your company data.

### Add a database connection

1. Go to **Settings** (top-right gear icon) → **Database Connections** → **+ Database**
2. Select your database type (PostgreSQL, MySQL, ClickHouse, BigQuery, etc.)
3. Enter the connection URI or fill in the form. Examples:

| Database | SQLAlchemy URI |
|---|---|
| PostgreSQL | `postgresql+psycopg2://user:pass@host:5432/dbname` |
| MySQL | `mysql+mysqlconnector://user:pass@host:3306/dbname` |
| ClickHouse | `clickhousedb://user:pass@host:8123/dbname` |
| BigQuery | `bigquery://project` (requires credentials file) |

> **Tip:** If the data source runs on the same Docker network or host machine, use `host.docker.internal` as the hostname (macOS/Windows) or the container service name.

4. Click **Test Connection**, then **Connect**

### Install additional database drivers

The base Superset image includes PostgreSQL and MySQL drivers. For other databases, create a custom Dockerfile:

```dockerfile
FROM apache/superset:4.1.1
USER root
RUN pip install clickhouse-connect mysqlclient
USER superset
```

Then update `docker-compose.yml` to build from this Dockerfile instead of using the image directly.

## Building Your First Dashboard

### Step 1 — Create a Dataset

1. Go to **SQL** → **SQL Lab**
2. Select your database and schema, write a query to explore your data
3. When you have a useful query, click **Save** → **Save as Dataset** (give it a clear name like `monthly_revenue`)

Alternatively: **Data** → **Datasets** → **+ Dataset** → pick a table directly.

### Step 2 — Create Charts

1. Go to **Charts** → **+ Chart**
2. Pick the dataset you just created
3. Choose a visualization type:
   - **Table** — quick data overview
   - **Big Number with Trendline** — KPIs
   - **Bar Chart / Line Chart** — time series and comparisons
   - **Pie Chart** — proportions
   - **Pivot Table** — multidimensional analysis
4. Configure metrics (e.g. `SUM(revenue)`), dimensions (e.g. `region`), and filters
5. Click **Run** to preview, then **Save**

### Step 3 — Assemble a Dashboard

1. Go to **Dashboards** → **+ Dashboard**
2. Click **Edit Dashboard** (pencil icon)
3. Drag saved charts from the right panel onto the canvas
4. Add **Tabs**, **Rows**, **Columns**, **Header**, and **Divider** layout elements
5. Add **Filters** (use the filter icon) so users can interactively slice the data
6. Click **Save**

### Step 4 — Share with your team

- Share the dashboard URL directly
- Set up **Roles** under **Settings** → **List Roles** to control who sees what
- Use **Row Level Security** for fine-grained data access

## Operations

### View logs

```bash
docker compose logs -f superset          # web server
docker compose logs -f superset-worker   # celery worker
```

### Restart after config changes

```bash
docker compose down
docker compose up -d
```

### Upgrade Superset

1. Update the image tag in `docker-compose.yml` (e.g. `apache/superset:4.2.0`)
2. Run:
   ```bash
   docker compose down
   docker compose up -d
   ```
   The `superset-init` container will automatically run new migrations.

### Backup metadata database

```bash
docker compose exec postgres pg_dump -U superset superset > backup_$(date +%F).sql
```

### Restore from backup

```bash
cat backup_2026-03-10.sql | docker compose exec -T postgres psql -U superset superset
```

## Production Checklist

- [ ] Set a strong `SUPERSET_SECRET_KEY` (and never change it after first run)
- [ ] Set strong passwords for admin and PostgreSQL
- [ ] Put Superset behind a reverse proxy (Nginx/Caddy) with HTTPS
- [ ] Enable `TALISMAN_ENABLED = True` in `superset_config.py` once HTTPS is in place
- [ ] Set `SESSION_COOKIE_SECURE = True` for HTTPS-only cookies
- [ ] Configure OAuth/LDAP for team authentication (instead of local accounts)
- [ ] Set up scheduled database backups
- [ ] Monitor container health and resource usage
- [ ] Restrict network access to Superset port (firewall / security groups)
