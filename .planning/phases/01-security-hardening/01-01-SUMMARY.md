---
phase: 01-security-hardening
plan: 01
subsystem: infra
tags: [caddy, tls, https, talisman, csp, docker, security]

requires: []
provides:
  - Caddy reverse proxy with internal TLS serving Superset at port 443
  - HTTP-to-HTTPS redirect on port 80
  - Superset port 8088 restricted to Docker-internal network only
  - Talisman CSP headers enabled with Superset-compatible policy
  - SESSION_COOKIE_SECURE and SESSION_COOKIE_SAMESITE=Strict
  - SECRET_KEY generation documented in superset_config.py
affects: [02-reliability, 03-dashboard-generation]

tech-stack:
  added: [caddy:2-alpine]
  patterns: [reverse-proxy-tls-termination, talisman-csp-hardening]

key-files:
  created:
    - docker/Caddyfile
  modified:
    - docker-compose.yml
    - docker/superset_config.py

key-decisions:
  - "Caddy over Nginx for reverse proxy — automatic TLS (internal), simpler config, zero-config HTTPS"
  - "tls internal for local deployment — self-signed cert, no domain required; switch to Let's Encrypt by removing tls internal directive"
  - "unsafe-inline and unsafe-eval kept in CSP script-src — required by Superset's React SPA, removing breaks UI"
  - "SESSION_COOKIE_SAMESITE upgraded from Lax to Strict — stricter CSRF protection now that HTTPS is enforced"
  - "Caddyfile uses hostname localhost instead of bare :443 — required for Caddy to serve on named host with tls internal"

patterns-established:
  - "Caddy volume mount pattern: ./docker/Caddyfile:/etc/caddy/Caddyfile:ro"
  - "Superset internal port via expose directive (not ports) — Caddy bridges external to internal"

requirements-completed: [SEC-01, SEC-02, SEC-03, SEC-04, SEC-05]

duration: ~15min
completed: 2026-03-26
---

# Phase 01 Plan 01: Security Hardening — HTTPS, TLS, Secure Cookies, CSP Summary

**Caddy reverse proxy with internal TLS termination, Superset port 8088 locked to Docker-internal network, Talisman CSP headers, and SESSION_COOKIE_SECURE=True with SameSite=Strict — all verified live via curl and browser**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-26T13:28:01Z
- **Completed:** 2026-03-26
- **Tasks:** 3 of 3 (all complete including human verification)
- **Files modified:** 3

## Accomplishments

- Created docker/Caddyfile: TLS internal, reverse_proxy superset:8088, security headers, HTTP-to-HTTPS redirect
- Added caddy service in docker-compose.yml on ports 80/443 with named volumes for cert persistence
- Removed host-exposed superset port 8088 (replaced with expose directive for Docker-internal use only)
- Enabled TALISMAN_ENABLED=True with full Superset-compatible CSP configuration
- Added SESSION_COOKIE_SECURE=True, upgraded SameSite from Lax to Strict
- Documented SECRET_KEY generation with openssl rand -base64 42 comment in superset_config.py
- Human verification passed: HTTPS 302, HTTP 308, port 8088 refused, CSP header present, security headers present

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Caddy reverse proxy and restrict Superset port exposure** - `5ecdf4b` (feat)
2. **Task 2: Enable Talisman, secure cookies, and verify SECRET_KEY documentation** - `df35949` (feat)
3. **Caddyfile syntax fix** - `3d58be1` (fix — deviation, see below)
4. **Task 3: Verify HTTPS, redirects, port isolation, and cookie flags** - VERIFIED (human-approved)

## Files Created/Modified

- `docker/Caddyfile` - Caddy reverse proxy config: TLS internal, reverse_proxy to superset:8088, HTTP redirect, security headers
- `docker-compose.yml` - Added caddy service (ports 80/443), removed host-exposed 8088, added caddy_data/caddy_config volumes
- `docker/superset_config.py` - TALISMAN_ENABLED=True with CSP, SESSION_COOKIE_SECURE=True, SameSite=Strict, SECRET_KEY comment

## Decisions Made

- Caddy chosen over Nginx: automatic TLS with zero config, simpler Caddyfile syntax
- Using `tls internal` (self-signed) for local/dev deployment; switching to Let's Encrypt requires only removing that line
- Kept `'unsafe-inline'` and `'unsafe-eval'` in CSP script-src — mandatory for Superset's React SPA
- Added `blob:` and `data:` to img-src for ECharts chart exports and base64 images
- Changed Caddyfile site address from `{:443}` to `localhost` — Caddy requires a hostname (not bare port) when using `tls internal`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Caddyfile syntax fix: bare :443 does not work with tls internal**
- **Found during:** Task 3 verification (stack startup)
- **Issue:** The plan specified `{:443}` as the site address, but Caddy requires a hostname (e.g., `localhost`) when using `tls internal`. Using a bare port causes Caddy to fail to issue an internal cert.
- **Fix:** Changed site address from `{:443}` to `localhost` in docker/Caddyfile
- **Files modified:** docker/Caddyfile
- **Verification:** `curl -kI https://localhost` returned HTTP/2 302 after fix; HTTP redirects as 308
- **Committed in:** `3d58be1` (fix: correct Caddyfile syntax)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential fix — stack would not start correctly with bare :443 and tls internal. No scope creep.

## Issues Encountered

None beyond the Caddyfile syntax issue documented above (handled automatically).

## User Setup Required

None - all verification passed. The stack is running and all security requirements are met.

## Verification Results (Task 3)

All 5 security requirements verified live:

| Requirement | Result |
|-------------|--------|
| SEC-01 | HTTPS works: `curl -kI https://localhost` returns HTTP/2 302 |
| SEC-01 | HTTP redirects: `curl -I http://localhost` returns 308 Permanent Redirect |
| SEC-02 | SECRET_KEY comment with openssl rand command present in superset_config.py |
| SEC-03 | Secure cookie flags set (SESSION_COOKIE_SECURE=True, SameSite=Strict) |
| SEC-04 | CSP header present: Content-Security-Policy in response headers |
| SEC-05 | Port 8088 refused from host (connection refused on curl http://localhost:8088) |

Additional headers confirmed: X-Content-Type-Options, X-Frame-Options, Referrer-Policy.

## Next Phase Readiness

- SEC-01 through SEC-05 all complete and live-verified
- Phase 02 (reliability: backups, resource limits, health monitoring) can proceed immediately
- Stack is running on Docker Compose with Caddy on 80/443

---
*Phase: 01-security-hardening*
*Completed: 2026-03-26*
