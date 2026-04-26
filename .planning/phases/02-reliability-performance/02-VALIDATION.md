---
phase: 02
slug: reliability-performance
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-27
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash / docker compose (infrastructure validation) |
| **Config file** | docker-compose.yml, .env |
| **Quick run command** | `docker compose config --quiet` |
| **Full suite command** | `docker compose config --quiet && grep -c 'deploy:' docker-compose.yml && grep -q 'curl.*8088/health' docker-compose.yml && grep -q 'eeshugerman/postgres-backup-s3' docker-compose.yml && grep -q '1800' docker/superset_config.py && grep -q 'S3_BUCKET' .env.example && grep -q 'CELERY_BROKER_URL' .env.example && echo "ALL CHECKS PASSED"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `docker compose config --quiet` (validates compose syntax)
- **After every plan wave:** Run full suite command above
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 02-01-01 | 01 | 1 | REL-02, REL-03, REL-04, CFG-01, CFG-02 | integration | `docker compose config --quiet && grep -c 'deploy:' docker-compose.yml && grep -q 'curl.*8088/health' docker-compose.yml && grep -q 'workers 5' docker-compose.yml && grep -q 'concurrency=4' docker-compose.yml` | ⬜ pending |
| 02-01-02 | 01 | 1 | REL-01, CFG-03 | integration | `docker compose config --quiet && grep -q 'eeshugerman/postgres-backup-s3' docker-compose.yml && grep -q 'S3_BUCKET' .env.example && grep -q 'CELERY_BROKER_URL' .env.example && grep -q '1800' docker/superset_config.py` | ⬜ pending |
| 02-01-03 | 01 | 1 | all | checkpoint | `docker compose config --quiet && docker compose ps --format json` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None — all plan tasks have concrete `<automated>` verify commands using docker compose and grep assertions. No external test scripts required.

*Existing docker compose infrastructure covers all validation needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Container auto-restart after failure | REL-04 | Requires killing container process | `docker kill superset-superset-1 && sleep 10 && docker compose ps` |
| Backup runs on cron schedule | REL-01 | Requires waiting for scheduled execution | Check backup sidecar logs after 24h |
| Backup files are .sql.gz (gzip) | D-04 | Requires actual backup execution or image docs | Trigger manual backup or verify from sidecar image docs — built-in behavior of eeshugerman/postgres-backup-s3 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands — no Wave 0 dependencies needed
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] No Wave 0 gaps — all verify blocks are concrete commands
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
