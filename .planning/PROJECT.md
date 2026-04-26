# Superset Production BI Platform

## What This Is

A production-ready Apache Superset deployment for a small team, running on Docker Compose with PostgreSQL as the data source. Includes a Claude-powered workflow for generating Superset dashboard JSON files from database schema, enabling rapid dashboard creation without manual chart building.

## Core Value

The team can access reliable, auto-generated BI dashboards over their PostgreSQL data — with minimal manual dashboard building effort.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Docker Compose orchestration with all services (web, celery, redis, postgres) — initial commit
- ✓ PostgreSQL metadata backend configured — initial commit
- ✓ Admin user creation via init script — initial commit
- ✓ External PostgreSQL data source connected via Superset UI — manual setup
- ✓ HTTPS termination via Caddy reverse proxy with internal TLS — Phase 1
- ✓ Secure secret key generation and management — Phase 1
- ✓ Secure session cookies and Talisman CSP headers — Phase 1

### Active

<!-- Current scope. Building toward these. -->
- [ ] Automated PostgreSQL metadata backups
- [ ] Container resource limits (memory, CPU)
- [ ] Health monitoring and alerting
- [ ] Claude-generated dashboard JSON files based on PostgreSQL schema
- [ ] Dashboard import workflow (JSON → Superset UI)
- [ ] Sample dashboards demonstrating Superset chart types and capabilities

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- SSO/OAuth integration — small team, local auth sufficient for now
- External managed PostgreSQL (RDS) — containerized DB is adequate at current scale
- External managed Redis — containerized Redis is adequate at current scale
- Mobile app or custom frontend — Superset's built-in UI is sufficient
- Real-time streaming dashboards — batch/refresh-based analytics is sufficient
- Superset API scripts for dashboard creation — using JSON import approach instead

## Context

- Superset 4.1.1 pinned in Docker Compose
- PostgreSQL data source already connected in Superset UI with real data
- The team wants to explore Superset's visualization capabilities through generated dashboards
- Superset supports dashboard JSON export/import natively — Claude can generate these JSON structures
- Dashboard JSON includes dataset definitions, chart configs (viz type, metrics, dimensions), layout, and filters

## Constraints

- **Deployment**: Docker Compose on a single host — no Kubernetes or multi-node orchestration
- **Team size**: Small team — security and access control should be practical, not enterprise-grade
- **Dashboard generation**: JSON export/import approach — no direct API integration needed
- **Data**: PostgreSQL is the only data source for now

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Docker Compose deployment | Simple, self-contained, fits team size | ✓ Good |
| JSON import for dashboards | Simpler than API scripts, reviewable before import, no auth token management | — Pending |
| Nginx/Caddy reverse proxy for HTTPS | Standard approach for TLS termination with Docker | — Pending |

---
*Last updated: 2026-03-27 after Phase 1 completion*
