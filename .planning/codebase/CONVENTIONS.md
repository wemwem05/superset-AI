# Coding Conventions

**Analysis Date:** 2026-03-26

## Project Scope

This project is a **self-hosted Apache Superset deployment** configured via Docker Compose. It consists primarily of:
- Configuration files (Python, shell scripts, YAML)
- Docker infrastructure setup
- GSD hooks for Claude Code integration
- No custom application code or tests

This document covers the conventions observed in configuration files and hook scripts.

## Naming Patterns

**Files:**
- Configuration files use lowercase with underscores: `superset_config.py`, `superset-init.sh`
- Docker-related files use lowercase with hyphens: `docker-compose.yml`, `superset-init.sh`
- Environment variables use UPPERCASE with underscores: `SUPERSET_SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_HOST`
- Hook scripts use kebab-case with `gsd-` prefix: `gsd-prompt-guard.js`, `gsd-context-monitor.js`

**Functions/Exports:**
- Python functions in `superset_config.py` use lowercase with underscores (PEP 8): imports are lowercase, variable assignments are lowercase
- Shell scripts use lowercase with underscores for function names and variables
- JavaScript hooks use lowercase with underscores: `stdinTimeout`, `warnData`, `configDir`

**Variables:**
- Constants use UPPERCASE: `WARNING_THRESHOLD`, `CRITICAL_THRESHOLD`, `AUTO_COMPACT_BUFFER_PCT`
- Local variables use camelCase in JavaScript: `isGsdActive`, `metricsPath`, `hookVersion`
- Environment variables are referenced as UPPERCASE with `os.environ[]` (Python) or `process.env.VAR` (Node.js)

**Types/Classes:**
- Python classes use PascalCase: `CeleryConfig` in `superset_config.py` (line 69)

## Code Style

**Formatting:**
- Python: Follows PEP 8 (implicit, via Apache Superset project standards)
- JavaScript: Consistent spacing, 2-space indentation in hook scripts
- Shell scripts: bash with `set -e` error handling
- YAML: 2-space indentation in `docker-compose.yml`

**Linting:**
- No explicit linting configuration found in project root
- Apache Superset uses its own linting (external to this deployment config)
- Project configuration files are not linted

**Line lengths:**
- Python comments maintain readable width (~80 chars for docstrings)
- Shell scripts use line continuations with `\` for long commands
- JavaScript hook scripts use ternary operators and multiline strings without strict line limits

## Import Organization

**Python (`superset_config.py`):**
1. Standard library: `import os`, `from datetime import timedelta`
2. No third-party or local imports (configuration file only)

**JavaScript (hook scripts):**
1. Built-in modules: `const fs = require('fs')`, `const path = require('path')`, `const os = require('os')`, `const { spawn } = require('child_process')`
2. No external npm dependencies used (self-contained scripts)

**Path references:**
- Python: Uses `os.environ[]` for environment variables, f-strings for interpolation
- JavaScript: Uses `path.join()` for cross-platform path construction
- No path aliases in use

## Error Handling

**Patterns:**
- Python: Direct environment variable access via `os.environ[]` with no fallback (fails fast if missing required config)
- Python: Uses `os.environ.get()` with defaults for optional vars (lines 34-35, 106)
- Shell scripts: Uses `set -e` to exit on first error, `|| true` for non-critical commands that are allowed to fail (line 14)
- JavaScript: Try-catch blocks with silent failures to prevent hook crashes:
  ```javascript
  try {
    // operation
  } catch (e) {
    // Silent fail — never block tool execution
    process.exit(0);
  }
  ```
- JavaScript: Timeout guards to prevent hanging pipes (3000-10000ms timeouts)

## Logging

**Framework:**
- Python: Apache Superset's built-in logging (managed externally)
- Shell scripts: `echo` statements for progress (lines 4, 7, 16, 20, 24)
- JavaScript: Logs via `process.stdout.write()` for JSON output to stdout, silent failures catch errors

**Patterns:**
- Shell init script logs each major phase: migration, admin creation, init, examples
- Hook scripts output structured JSON to stdout for consumption by GSD orchestrator
- Hook scripts fail silently (exit code 0) to avoid blocking operations
- Errors logged to `/tmp/` bridge files for inter-process communication (lines 40, 87-88, 110 in gsd-statusline.js)

## Comments

**When to Comment:**
- Configuration rationale provided in docstrings (line 1-4 in `superset_config.py`)
- Complex shell logic explained inline (line 14 in `superset-init.sh`: `|| true`)
- Hook version tracking via header comment: `// gsd-hook-version: 1.29.0` (all hooks)
- Security/production notes in Python config (lines 90-103)

**JSDoc/TSDoc:**
- Not used in this project (configuration-focused, minimal function definitions)
- Hook scripts have descriptive comments at top with purpose and trigger conditions

## Function Design

**Size:**
- Functions not the primary focus (mostly procedural configuration)
- Hook scripts use main logic blocks with guards and early exits

**Parameters:**
- Python configuration uses environment variable injection (no function parameters in config)
- JavaScript hooks read from stdin JSON, parse structured input

**Return Values:**
- Python: No function returns (configuration assignments only)
- JavaScript: Return status via `process.exit(0)` or `process.exit(1)`, structured output to stdout via JSON
- Hook scripts return immediately on non-applicable conditions (guard clauses)

## Module Design

**Exports:**
- Python: Single configuration module `superset_config.py` is imported as a whole by Superset
- No explicit exports (configuration variables are module-level)
- JavaScript hooks: Standalone scripts executed by GSD, output via stdout

**Barrel Files:**
- Not used in this project

## Configuration Files

**Environment Configuration:**
- All secrets and environment-specific values in `.env` (gitignored)
- Template provided in `.env.example`
- Environment variables documented with comments in example file

**Docker Compose Structure:**
- YAML anchors (`&superset-common`, `<<: *superset-common`) reduce duplication across service definitions
- Health checks defined for database and cache dependencies (lines 26-30, 40-44)
- Service dependencies specified with `depends_on` and `condition` checks (lines 10-14)

## Style Summary

This is a **configuration-heavy project** with minimal custom code:
- Python config emphasizes readability and environment-driven settings
- Shell scripts prioritize robustness (`set -e`) and clear progress reporting
- JavaScript hooks prioritize stability (silent failures, timeout guards) and inter-process communication
- YAML uses structural clarity via anchors and indentation
- Documentation embedded in comments for complex/non-obvious logic

---

*Convention analysis: 2026-03-26*
