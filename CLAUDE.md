# Superset BI Platform

Self-hosted Apache Superset deployment for production BI use, running on Docker Compose.

## Project Structure

- `docker-compose.yml` — orchestrates all services (superset web, celery worker, celery beat, init, postgres, redis)
- `.env` / `.env.example` — all environment variables (secrets, DB credentials, feature toggles)
- `docker/superset_config.py` — Superset Python config (caching, celery, security, feature flags)
- `docker/superset-init.sh` — one-shot init script: DB migrations + admin user creation

## How It Works

`docker compose up -d` starts everything. The `superset-init` container runs migrations and creates the admin user, then exits. The web server (gunicorn), celery worker, and celery beat start after init completes. PostgreSQL stores metadata, Redis handles caching and serves as the Celery broker.

## Key Commands

- `docker compose up -d` — start
- `docker compose down` — stop
- `docker compose logs -f superset` — web logs
- `docker compose exec postgres pg_dump -U superset superset > backup.sql` — backup

## Productionization Recommendations

### Security (critical)

- **HTTPS**: Place Superset behind a reverse proxy (Nginx, Caddy, or cloud LB) with TLS termination. Then enable `TALISMAN_ENABLED = True` and `SESSION_COOKIE_SECURE = True` in `superset_config.py`.
- **Secrets**: Generate `SUPERSET_SECRET_KEY` with `openssl rand -base64 42`. Never reuse or rotate it after first deployment — it encrypts saved DB credentials. Use a secrets manager (Vault, AWS Secrets Manager) instead of plain `.env` in production.
- **Authentication**: Replace local accounts with SSO (OAuth2/OIDC) or LDAP. Superset supports Google, Okta, Azure AD, Keycloak out of the box via Flask-AppBuilder security manager.
- **Row-Level Security**: Configure RLS policies so teams only see their own data.
- **Network**: Restrict port 8088 to internal network only. Expose through reverse proxy. Keep postgres and redis ports unexposed (they already are in the current compose file).

### Reliability

- **Database backups**: Schedule daily `pg_dump` via cron or a sidecar container. Store backups offsite (S3, GCS).
- **Persistent volumes**: The compose file uses named volumes. On production, back these with durable storage (EBS, persistent disks).
- **Health monitoring**: Add monitoring (Prometheus + Grafana, Datadog, etc.) for container health, response times, and resource usage. Superset exposes a `/health` endpoint.
- **Resource limits**: Add `mem_limit` and `cpus` to each service in `docker-compose.yml` to prevent a single service from starving others.

### Performance

- **Gunicorn workers**: Currently set to 4. Tune to `2 * CPU_CORES + 1` for the host machine.
- **Celery concurrency**: Currently 2 prefork workers. Increase based on async query volume.
- **Cache TTLs**: Tune `CACHE_DEFAULT_TIMEOUT` in `superset_config.py` based on how frequently your source data updates.
- **Query result caching**: Already configured with Redis. For large datasets, consider adding a dedicated results backend (S3).

### Scalability

- **External PostgreSQL**: For production, migrate the metadata DB to a managed service (RDS, Cloud SQL) instead of the containerized instance.
- **External Redis**: Similarly, use managed Redis (ElastiCache, Memorystore) for better reliability.
- **Multiple workers**: Scale celery workers with `docker compose up -d --scale superset-worker=3`.
- **Load balancing**: If scaling the web tier, run multiple `superset` containers behind a load balancer with sticky sessions.

### CI/CD & Operations

- **Version pinning**: The image is pinned to `apache/superset:4.1.1`. Test upgrades in staging before production.
- **Config as code**: Keep `superset_config.py` and `docker-compose.yml` in version control. Keep `.env` out (gitignored).
- **Staged rollouts**: When upgrading, bring up the new version alongside the old, run `superset db upgrade` via the init container, then switch traffic.
