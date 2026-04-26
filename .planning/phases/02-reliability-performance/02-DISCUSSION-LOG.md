# Phase 2: Reliability & Performance Tuning - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 02-reliability-performance
**Areas discussed:** Backup strategy, Resource limits, Health monitoring

---

## Backup Strategy

### Backup destination

| Option | Description | Selected |
|--------|-------------|----------|
| Local volume | Store pg_dump in Docker named volume or bind-mounted directory | |
| S3-compatible storage | Upload to S3, MinIO, or similar. Offsite by default. | ✓ |
| Host bind mount | Mount specific host directory for manual offsite copy | |

**User's choice:** S3-compatible storage
**Notes:** None

### Retention policy

| Option | Description | Selected |
|--------|-------------|----------|
| 7 days | One week of daily backups. Good balance of safety and storage. | ✓ |
| 14 days | Two weeks of daily backups. More recovery window. | |
| 30 days | Full month. Maximum safety net, higher cost. | |

**User's choice:** 7 days
**Notes:** None

### Scheduling mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Sidecar container with cron | Lightweight container in docker-compose.yml. Self-contained. | ✓ |
| Host crontab | Cron entry on host machine. Simpler but host-dependent. | |

**User's choice:** Sidecar container with cron
**Notes:** None

### Compression

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, gzip | Compress before upload. 5-10x smaller. | ✓ |
| No compression | Raw SQL dump. Larger but simpler. | |

**User's choice:** Yes, gzip
**Notes:** None

---

## Resource Limits

### Host machine specs

| Option | Description | Selected |
|--------|-------------|----------|
| 4 CPU / 8 GB RAM | Small VPS | |
| 8 CPU / 16 GB RAM | Mid-range server | |
| 16+ CPU / 32+ GB RAM | Large server | |

**User's choice:** AWS EC2 r6a.4xlarge (16 vCPUs, 128 GB RAM)
**Notes:** Shared with Airflow running heavy tasks. Current usage: 24% CPU, 12% memory. Keeping the machine alive is critical.

### Total resource budget

| Option | Description | Selected |
|--------|-------------|----------|
| 25% of machine | ~4 vCPUs / 32 GB. Leaves 75% for Airflow and OS. | ✓ |
| 15% of machine | ~2.5 vCPUs / 19 GB. Very conservative. | |
| 40% of machine | ~6 vCPUs / 51 GB. More room for Superset. | |

**User's choice:** 25% of machine
**Notes:** None

---

## Health Monitoring

### Monitoring level

| Option | Description | Selected |
|--------|-------------|----------|
| Docker healthchecks only | Healthcheck directives in docker-compose.yml. Docker handles restarts. | ✓ |
| Healthchecks + alerting | Docker healthchecks plus notification script. | |
| Full monitoring stack | Prometheus + Grafana. Out of scope for v1. | |

**User's choice:** Docker healthchecks only
**Notes:** None

### Health check depth

| Option | Description | Selected |
|--------|-------------|----------|
| Just /health endpoint | curl localhost:8088/health. Simple and reliable. | ✓ |
| Multi-check script | Check /health + DB + Redis. More thorough but complex. | |

**User's choice:** Just /health endpoint
**Notes:** None

---

## Claude's Discretion

- Performance tuning values (Gunicorn workers, Celery concurrency, cache TTLs) — user chose not to discuss
- Exact per-service resource limit distribution within 25% budget
- Backup cron schedule time
- S3 bucket naming and path structure
- Backup sidecar container image choice

## Deferred Ideas

None — discussion stayed within phase scope.
