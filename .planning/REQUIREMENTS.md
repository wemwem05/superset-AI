# Requirements: Superset Production BI Platform

**Defined:** 2026-03-26
**Core Value:** The team can access reliable, auto-generated BI dashboards over their PostgreSQL data

## v1 Requirements

Requirements for initial production deployment and dashboard generation capability.

### Security

- [x] **SEC-01**: HTTPS termination via Caddy reverse proxy with automatic TLS certificates
- [x] **SEC-02**: Superset SECRET_KEY generated securely and stored outside docker-compose.yml
- [x] **SEC-03**: Secure session cookies enabled (SESSION_COOKIE_SECURE, SESSION_COOKIE_HTTPONLY)
- [x] **SEC-04**: Talisman CSP headers enabled for XSS protection
- [x] **SEC-05**: Superset web port (8088) not exposed externally — only accessible through reverse proxy

### Reliability

- [x] **REL-01**: Automated daily PostgreSQL metadata backup with retention policy
- [x] **REL-02**: Container resource limits (memory, CPU) for all services
- [x] **REL-03**: Health monitoring via Superset /health endpoint
- [x] **REL-04**: Docker Compose restart policies for all services

### Dashboard Generation

- [ ] **DASH-01**: Python script to generate Superset-compatible ZIP export (YAML structure) from database schema
- [ ] **DASH-02**: Generated ZIP includes valid metadata.yaml, database, dataset, chart, and dashboard YAML files
- [ ] **DASH-03**: Generated dashboards use stable UUIDs (deterministic from table/column names)
- [ ] **DASH-04**: Generated charts cover core viz types: table, bar chart, line chart, pie chart
- [ ] **DASH-05**: Generated dashboard layout positions charts in a readable grid
- [ ] **DASH-06**: Import workflow documented — user can import generated ZIP via Superset UI
- [ ] **DASH-07**: Script connects to PostgreSQL to introspect schema (tables, columns, types)

### Configuration

- [x] **CFG-01**: Gunicorn workers tuned for host machine (2 * CPU + 1)
- [x] **CFG-02**: Celery concurrency configured for small team usage
- [x] **CFG-03**: Cache TTLs configured appropriately in superset_config.py

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Dashboard Generation

- **DASH-08**: Support for time-series charts with automatic date column detection
- **DASH-09**: Support for cross-filtering between charts
- **DASH-10**: Dashboard templates for common analytics patterns (sales, ops, user analytics)
- **DASH-11**: CLI tool to auto-import generated ZIPs without UI interaction

### Advanced Security

- **SEC-06**: SSO/OAuth integration (Google, Okta, or Keycloak)
- **SEC-07**: Row-level security policies per team

### Advanced Reliability

- **REL-05**: External managed PostgreSQL migration (RDS/Cloud SQL)
- **REL-06**: External managed Redis migration (ElastiCache/Memorystore)
- **REL-07**: Prometheus + Grafana monitoring stack

## Out of Scope

| Feature | Reason |
|---------|--------|
| Custom Superset plugins | Adds frontend build complexity, stock charts are sufficient |
| Mobile app | Superset responsive UI is sufficient for small team |
| Real-time streaming | Batch refresh is sufficient for current needs |
| Multi-node deployment | Single Docker Compose host is adequate at this scale |
| Superset REST API integration | ZIP import via UI is simpler and more reviewable |
| Kubernetes migration | Docker Compose is sufficient for small team |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Complete |
| SEC-02 | Phase 1 | Complete |
| SEC-03 | Phase 1 | Complete |
| SEC-04 | Phase 1 | Complete |
| SEC-05 | Phase 1 | Complete |
| REL-01 | Phase 2 | Complete |
| REL-02 | Phase 2 | Complete |
| REL-03 | Phase 2 | Complete |
| REL-04 | Phase 2 | Complete |
| CFG-01 | Phase 2 | Complete |
| CFG-02 | Phase 2 | Complete |
| CFG-03 | Phase 2 | Complete |
| DASH-01 | Phase 3 | Pending |
| DASH-02 | Phase 3 | Pending |
| DASH-03 | Phase 3 | Pending |
| DASH-04 | Phase 3 | Pending |
| DASH-05 | Phase 3 | Pending |
| DASH-06 | Phase 3 | Pending |
| DASH-07 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after initial definition*
