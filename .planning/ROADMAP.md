# Roadmap: Superset Production BI Platform

**Milestone:** v1.0 — Production Deployment + Dashboard Generation
**Created:** 2026-03-26
**Phases:** 3

---

## Phase 1: Security Hardening

**Goal:** Superset accessible only via HTTPS with proper secret management and security headers.

**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04, SEC-05

**Plans:** 1/1 plans complete

Plans:
- [x] 01-01-PLAN.md — HTTPS via Caddy reverse proxy, secure cookies, Talisman CSP, port isolation

**Deliverables:**
- Caddy reverse proxy added to docker-compose.yml with automatic TLS
- Securely generated SECRET_KEY stored in .env
- superset_config.py updated with Talisman, secure cookies, CSRF
- Port 8088 unexposed externally (internal Docker network only)

**Success criteria:**
- Superset loads over HTTPS with valid certificate
- HTTP requests redirect to HTTPS
- Direct access to port 8088 from outside Docker network fails
- Browser shows secure cookie flags in DevTools

**Status:** ◐ Planning complete

---

## Phase 2: Reliability & Performance Tuning

**Goal:** Superset deployment is resilient with automated backups, resource limits, and tuned performance.

**Requirements:** REL-01, REL-02, REL-03, REL-04, CFG-01, CFG-02, CFG-03

**Plans:** 1/1 plans complete

Plans:
- [x] 02-01-PLAN.md — Resource limits, healthchecks, S3 backup sidecar, Gunicorn/Celery tuning, cache TTLs

**Deliverables:**
- Backup script with daily cron schedule for PostgreSQL metadata
- Resource limits (mem_limit, cpus) added to all services in docker-compose.yml
- Health check endpoint monitored
- Restart policies configured
- Gunicorn workers and Celery concurrency tuned
- Cache TTLs configured in superset_config.py

**Success criteria:**
- pg_dump backup runs successfully and produces valid SQL file
- docker stats shows containers respecting resource limits
- curl to /health returns 200
- Containers auto-restart after simulated failure
- Gunicorn workers match host CPU count formula

**Status:** ◐ Planning complete

---

## Phase 3: Claude Dashboard Generation

**Goal:** Python script generates valid Superset dashboard ZIP from PostgreSQL schema, ready for UI import.

**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DASH-07

**Deliverables:**
- Python script that connects to PostgreSQL and introspects schema
- Generates Superset v1 export ZIP with proper YAML structure
- Stable deterministic UUIDs from table/column names
- Charts: table view, bar chart, line chart, pie chart per table
- Dashboard layout with grid positioning
- Documentation: how to run script and import ZIP into Superset

**Success criteria:**
- Script runs against connected PostgreSQL and produces valid ZIP
- ZIP imports successfully via Superset UI without errors
- Imported dashboard shows charts with real data from the database
- Charts are readable with proper titles, axes, and formatting
- Re-running script produces same UUIDs (no duplicate objects on re-import)

**Status:** ○ Pending

---

## Phase Summary

| Phase | Name | Requirements | Status |
|-------|------|-------------|--------|
| 1 | 1/1 | Complete   | 2026-03-26 |
| 2 | 1/1 | Complete   | 2026-03-27 |
| 3 | Dashboard Generation | DASH-01..07 | ○ Pending |

**Total v1 requirements:** 19
**Phases:** 3
**Coverage:** 100% ✓

---
*Roadmap created: 2026-03-26*
*Last updated: 2026-03-27 after Phase 2 planning*
