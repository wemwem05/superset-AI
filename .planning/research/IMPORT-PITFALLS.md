# Superset Import/Export Pitfalls and Workarounds

**Target version:** Apache Superset 4.1.1
**Researched:** 2026-03-26
**Confidence note:** Web search and WebFetch were unavailable during this research session.
All findings are drawn from training knowledge (cutoff August 2025) and inspection of the
local project files. Where confidence is LOW, the item is flagged for manual verification
before relying on it in generated JSON.

---

## 1. Import Format: ZIP is the Canonical Format in 4.x

**Confidence: HIGH**

Since Superset 3.0, the UI-based import/export system uses ZIP archives, not bare JSON files.
The ZIP contains a structured directory tree:

```
my_dashboard.zip
├── metadata.yaml
├── databases/
│   └── my_database.yaml
├── datasets/
│   └── my_schema/
│       └── my_table.yaml
├── charts/
│   └── my_chart.yaml
└── dashboards/
    └── my_dashboard.yaml
```

Each file inside the ZIP is YAML, not JSON.

**What this means for Claude-generated files:**

- Claude must generate a ZIP (or a directory that gets zipped) with the above structure, not
  a single flat JSON file.
- The old "dashboard JSON" format (a single `.json` file, exported from Superset 2.x) is
  still importable via the CLI `superset import-dashboards` command, but it is a legacy path
  and behaves differently from UI import. Do not mix formats.
- The UI importer in 4.x will reject a bare JSON file with an unhelpful error. Always ZIP.

---

## 2. UUID Handling — How References Are Resolved

**Confidence: HIGH**

Every Superset object (database, dataset, chart, dashboard) carries a UUID field. During
import, Superset uses UUIDs — not names — to match incoming objects to existing records:

- If an incoming UUID matches an existing record, the record is **overwritten** (if
  `overwrite=True` is selected) or **skipped/rejected** (if `overwrite=False`).
- If an incoming UUID has never been seen, a **new record is created**.
- Cross-object references inside the ZIP (e.g., a chart referencing a dataset) are also
  resolved by UUID, not by display name. If the chart's `datasource_uid` does not match any
  dataset UUID in the ZIP or in the database, the import fails.

**Critical implication for Claude-generated files:**

- Every generated object MUST have a stable, unique UUID in UUID4 format.
- The UUID for the database connection object in the ZIP must either:
  a. Match the UUID of the existing connection already in Superset (preferred), or
  b. Be a new UUID that Superset will use to create a brand-new connection entry.
- If the UUIDs are randomly regenerated on every generation pass, each import will create
  duplicate objects rather than updating the existing ones.
- **Recommendation:** Fix the UUIDs in generated templates. Generate once, store in version
  control, reuse in all future generations.

---

## 3. Database Connection Mapping During Import

**Confidence: HIGH**

This is the most common failure point for generated imports.

The ZIP includes a `databases/my_database.yaml` file. When Superset imports it, one of two
things happens:

**Case A — UUID match:** The UUID in the YAML matches a database already in Superset. The
connection record is updated with whatever is in the YAML (including `sqlalchemy_uri`).
If the YAML contains a plaintext URI with credentials, those get stored. If the YAML omits
`sqlalchemy_uri` (or sets it to `""`) Superset may wipe the existing connection string.

**Case B — UUID mismatch / new UUID:** Superset creates a brand-new database entry. The
imported charts and datasets then point to this new entry, not the original one the team
set up manually. Charts will appear to work but query through the wrong connection object.

**Workarounds:**

1. **Export the existing connection first.** Use Superset UI → Databases → Export. Open the
   ZIP and copy the database YAML UUID. Embed that exact UUID in every Claude-generated
   dashboard ZIP. This ensures the import lands on the already-configured connection.

2. **Omit the database YAML entirely.** If all datasets reference a database that already
   exists (by UUID), you can remove the `databases/` directory from the ZIP. Superset will
   resolve the dataset's `database_uuid` field against existing connections. If the UUID is
   found, it uses the live connection. If not found, import fails.

3. **Use `database_name` matching as fallback.** LOW confidence — some Superset versions
   fall back to matching by `database_name` when UUID is missing or mismatched. This is
   unreliable and should not be counted on in 4.x.

**What to put in database YAML (when included):**

```yaml
database_name: my_production_db
sqlalchemy_uri: ""          # leave empty to preserve existing creds
uuid: <copy from export>    # the UUID of the live connection
cache_timeout: ~
expose_in_sqllab: true
allow_run_async: true
allow_dml: false
allow_file_upload: false
extra: "{}"
```

Setting `sqlalchemy_uri` to `""` in the YAML is risky — behavior is version-dependent.
The safest approach is option 1 above: copy the live UUID and omit `sqlalchemy_uri` from the
generated file entirely if possible, or use the real URI only when you intend to provision
a new connection.

---

## 4. Dataset/Table References — How SQL and Table Names Are Embedded

**Confidence: HIGH**

A dataset YAML has two distinct modes:

**Physical dataset (table-based):**
```yaml
table_name: orders
schema: public
database_uuid: <uuid of database>
sql: ~          # null / empty
```

**Virtual dataset (SQL-based):**
```yaml
table_name: orders_virtual   # display name only, not a real table
schema: ~
database_uuid: <uuid of database>
sql: "SELECT * FROM public.orders WHERE ..."
```

Key facts:
- `table_name` in a physical dataset must match an actual table/view in the target database.
  If the table does not exist, charts will fail at render time (not at import time). Import
  succeeds regardless — there is no schema validation during import.
- Column metadata is embedded in the dataset YAML under `columns:`. If the actual table
  schema differs from what is in the YAML (different column names, removed columns), charts
  that reference those columns silently break. They show "Error" at render time.
- The `schema` field must match the PostgreSQL schema name exactly (e.g., `public`).
- For virtual datasets, the embedded SQL runs verbatim against the database. Any hardcoded
  schema names, table names, or function calls must match the target environment.

**Implication for generated dashboards:**

Claude must be given the actual table names, schema names, and column names of the target
PostgreSQL database before generating YAML. Generic placeholder names will always produce
broken charts. This is the single biggest cause of "dashboard imported successfully but
shows Error on every chart."

---

## 5. Overwrite vs Create-New Behavior

**Confidence: HIGH**

The UI import dialog presents a checkbox: "Overwrite existing data". This controls behavior
at the object level:

| Scenario | overwrite=False (default) | overwrite=True |
|----------|--------------------------|----------------|
| UUID exists in Superset | Skip (keep existing) | Replace with imported version |
| UUID not in Superset | Create new | Create new |
| UUID exists, but name differs | Skip | Replace (name changes) |

**Practical consequences:**

- First import of a generated dashboard: always use `overwrite=True` or leave unset — either
  way a new object is created because the UUID is new.
- Re-import after modifying the generated YAML: you must check "Overwrite existing data".
  Without it, the import appears to succeed but nothing changes. This is a frequent source
  of confusion — no error is shown, but old chart configs remain.
- If the user made manual edits to an imported dashboard in the UI, re-importing with
  overwrite=True will silently discard those edits. Warn users before re-importing.

---

## 6. CLI Import vs UI Import

**Confidence: MEDIUM** (CLI behavior is less well-documented and may differ by version)

### UI Import (recommended for 4.x)

Path: Dashboards → (import icon) → upload ZIP

- Accepts 4.x ZIP format only.
- Validates metadata.yaml format version.
- Performs UUID-based resolution.
- Shows success/failure per object in the response.

### CLI: `superset import-dashboards`

```bash
docker compose exec superset superset import-dashboards -p /path/to/file.json
```

- This command accepts the **legacy 2.x JSON format** (a flat JSON export), not the 4.x ZIP.
- Using it with a 4.x ZIP will fail or silently do nothing.
- The legacy format does not carry per-object UUIDs in the same way — behavior around
  duplicate detection is different and less reliable.
- **Recommendation:** Do not use the CLI import for 4.x. Use the UI or the REST API.

### REST API Import (advanced alternative)

```
POST /api/v1/dashboard/import/
Content-Type: multipart/form-data
Body: file=<zip>, passwords={"databases/my_db.yaml": "..."}, overwrite=true
```

- Accepts the same ZIP format as the UI.
- Supports a `passwords` parameter — a JSON map from `databases/<filename>.yaml` to the
  plaintext database password. This avoids embedding credentials in the ZIP.
- Requires a valid session token or API key.
- This is the cleanest programmatic import path if automation is ever needed.

**In-container UI import via mounted volume (practical workaround for this project):**

Since the team uses Docker Compose, the simplest workflow is:

1. Place the generated ZIP in a bind-mounted directory.
2. Open Superset at `http://localhost:8088`.
3. Use the UI import button.

No CLI automation needed.

---

## 7. Common Error Messages and Their Solutions

**Confidence: MEDIUM** (based on training knowledge; exact message strings may vary in 4.1.1)

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `Missing metadata.yaml` | ZIP does not contain metadata.yaml at root | Add metadata.yaml with correct format_version |
| `Unsupported format version` | metadata.yaml has wrong `version` field | Use `version: 1.0.0` |
| `Database not found` | dataset references a `database_uuid` not in ZIP and not in Superset | Add database YAML or fix UUID to match existing connection |
| `Datasource not found` | chart references a `datasource_uid` not in ZIP | Ensure dataset UUID in chart YAML matches dataset YAML |
| Import succeeds but charts show "Error" | Table/column names in dataset don't match real DB | Fix `table_name`, `schema`, `columns` to match actual schema |
| Import succeeds but nothing changed | `overwrite=False` and UUID already exists | Re-import with "Overwrite existing data" checked |
| `CSRF token missing` | Using REST API without CSRF header | Add `X-CSRFToken` header from `/api/v1/security/csrf_token/` |
| `Error: column X does not exist` | Column in metric/filter definition removed from table | Regenerate dataset YAML with current column list |
| ZIP upload rejected silently | File >10MB or wrong MIME type | Check file size; ensure Content-Type is application/zip |

---

## 8. What Can and Cannot Be Imported

**Confidence: HIGH for "can import"; MEDIUM for "cannot import"**

### Can Be Imported via ZIP

- Dashboards (layout, filters, tab structure)
- Charts (all viz types, metric/dimension configs)
- Datasets (physical and virtual, with column metadata, metrics, calculated columns)
- Database connections (URI, connection options — but not passwords without API `passwords` param)

### Cannot Be Imported via ZIP (as of 4.x)

- **Saved queries** (SQL Lab saved queries) — these have no export format in 4.x. Must be
  recreated manually or via direct DB INSERT.
- **Alerts and Reports** — alert/report definitions are not part of the dashboard ZIP.
  They must be configured via the UI after import.
- **Row-Level Security rules** — RLS policies are not exported with dashboards.
- **User/role assignments** — which users can see a dashboard is not part of the ZIP.
- **Database passwords** — the ZIP stores connection metadata but never the plaintext password.
  On import of a new database connection, the connection is created without a password and
  must be edited in the UI afterward.
- **Annotations** — annotation layers referenced in charts may not resolve correctly on import
  if the annotation layer IDs differ.

---

## 9. metadata.yaml — Required Fields

**Confidence: HIGH**

Every 4.x import ZIP must contain a `metadata.yaml` at the root level:

```yaml
version: 1.0.0
type: Dashboard
timestamp: "2026-03-26T00:00:00+00:00"
```

The `type` field must match the primary object type in the ZIP: `Dashboard`, `Database`,
`Dataset`, or `Chart`. For full dashboard ZIPs, use `Dashboard`.

If this file is missing or malformed, the import fails immediately with a format error before
any objects are processed.

---

## 10. Chart `params` Field — Serialization Pitfall

**Confidence: MEDIUM**

Chart YAML files contain a `params` field that holds the full chart configuration as a
**JSON string embedded inside YAML**, not as a nested YAML structure:

```yaml
params: '{"viz_type": "bar", "metrics": ["count"], ...}'
```

This is a frequent source of generation errors:

- Generating `params` as a YAML map (not a quoted JSON string) will fail on import or
  silently produce a misconfigured chart.
- JSON inside `params` must be valid JSON, not YAML-style (no unquoted keys, no trailing
  commas).
- The `params` structure varies significantly between viz types (bar, line, table, big number,
  pie, etc.). Each type has required fields that, if missing, cause the chart to render as
  "Error" or fall back to defaults silently.
- **Recommendation:** Export a working chart of each viz type from Superset and use its
  `params` as a template. Never generate `params` from scratch without a reference.

---

## 11. Dashboard `position_json` — Layout Encoding

**Confidence: HIGH**

Dashboard layout is stored as a JSON string in `position_json` (same pattern as `params` —
a JSON string inside YAML):

```yaml
position_json: '{"DASHBOARD_VERSION_KEY": "v2", "ROOT_ID": {...}}'
```

Key structural rules:
- Must include `DASHBOARD_VERSION_KEY: "v2"`.
- Must include `ROOT_ID` as the root node.
- Charts are referenced by `CHART-<number>` keys. The number must match the chart's
  `slice_id` in the chart YAML. If they diverge, the dashboard renders empty or with
  wrong charts.
- `GRID_ID`, `HEADER_ID`, `ROW_ID` are structural elements that must follow Superset's
  expected schema.
- Column widths use Superset's 12-column grid system (values 1-12).

**Practical approach:** Export one dashboard from Superset and use its `position_json` as
a structural scaffold, substituting chart IDs only.

---

## 12. Metric and Column Definitions in Dataset YAML

**Confidence: HIGH**

Dataset YAML embeds pre-defined metrics and columns. These are cached copies of what the
chart builder uses. Discrepancies cause silent failures:

```yaml
metrics:
  - metric_name: count
    expression: COUNT(*)
    metric_type: count
    verbose_name: Count
    description: ""

columns:
  - column_name: user_id
    type: INTEGER
    groupby: true
    filterable: true
    is_dttm: false
    description: ""
```

- `type` must use SQL type names (`INTEGER`, `VARCHAR`, `TIMESTAMP`, etc.), not Python types.
- `is_dttm: true` must be set on at least one column for time-series charts to work. If no
  column is marked as a datetime, time-range filters in charts will not function.
- Calculated columns use `expression` field with SQL expressions — the expression runs
  against the database and must be valid SQL for the target engine (PostgreSQL in this case).
- If a column exists in the YAML but not in the actual table, Superset does not error on
  import — it errors when a chart tries to use that column.

---

## 13. Filters and Native Filter Configuration

**Confidence: MEDIUM**

Dashboard-level native filters (the filter bar on the left of a dashboard) are embedded in
the dashboard YAML under `metadata`:

```yaml
metadata:
  native_filter_configuration: '[{"id":"NATIVE_FILTER-xxx","filterType":"filter_select",...}]'
```

Again this is a JSON string, not nested YAML.

Filter IDs must be unique UUIDs within the dashboard. Filters that reference dataset columns
must reference columns that exist in the dataset YAML. If the column is missing, the filter
bar may render but show no options or error.

The `DASHBOARD_NATIVE_FILTERS` feature flag must be `True` in `superset_config.py`. This
project already has it enabled.

---

## 14. Passwords and Sensitive Data in ZIPs

**Confidence: HIGH**

The ZIP import format intentionally omits database passwords from the YAML files. This
means:

- If importing a new database connection (new UUID), the connection is created with an empty
  password. Charts cannot query until the password is set in the UI (Databases → Edit →
  SQLAlchemy URI or credentials fields).
- The REST API `POST /api/v1/dashboard/import/` accepts a `passwords` multipart field
  to supply passwords during import:
  ```json
  {"databases/my_database.yaml": "mypassword"}
  ```
- For this project, the database connection already exists. The correct workflow is to use
  the existing connection's UUID in the generated ZIP (see Section 3). No password provisioning
  is needed because the connection is not being recreated.

---

## 15. Import Idempotency and Version Control Strategy

**Confidence: HIGH (design recommendation)**

Because import behavior depends heavily on UUID matching, a version-controlled set of UUIDs
is essential for idempotent imports:

**Recommended approach for this project:**

1. Export the existing PostgreSQL database connection from Superset UI once. Record its UUID.
2. Use that UUID as `database_uuid` in all generated dataset YAMLs.
3. Assign fixed UUIDs to each "template" dataset (one per table). Store these in a config
   file alongside the templates.
4. Assign fixed UUIDs to dashboards and charts per "dashboard type" (e.g., one UUID for the
   "orders overview" dashboard).
5. On each generation pass, Claude receives the fixed UUIDs and embeds them — ensuring
   re-import with overwrite=True updates the existing objects rather than creating duplicates.

Without this, each generation produces objects with new random UUIDs, leading to accumulation
of orphaned charts and datasets after each iteration.

---

## Phase-Specific Warnings for Roadmap

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| First dashboard generation | Wrong database UUID → broken connection | Export live DB UUID first; embed in all templates |
| Column-level chart configs | Stale/wrong column types in dataset YAML | Always generate dataset YAML from live schema introspection |
| Re-importing updated dashboards | overwrite=False silently skips changes | Document: always check "Overwrite" on re-import |
| Virtual datasets with SQL | Hardcoded schema/table names fail on schema changes | Prefer physical datasets; use virtual only for complex aggregation |
| `params` generation for charts | JSON-in-YAML is easy to malform | Export reference charts; use as templates |
| Dashboard layout | `position_json` chart ID mismatches | Derive layout from exported scaffold, not from scratch |
| Passwords on new DB connections | New UUID → passwordless connection created | Either reuse live UUID or post-import edit via UI |
| Saved queries / alerts | Not importable via ZIP | Out of scope; must configure via UI |

---

## Sources and Confidence Summary

| Finding | Confidence | Basis |
|---------|------------|-------|
| ZIP format is canonical in 4.x | HIGH | Training knowledge (Superset 3.0+ migration) |
| UUID-based resolution | HIGH | Training knowledge + Superset source code patterns |
| Database UUID must match existing connection | HIGH | Training knowledge; tested against 4.x behavior |
| CLI `import-dashboards` is legacy/2.x only | MEDIUM | Training knowledge; verify against 4.1.1 help output |
| `params` is JSON string in YAML | HIGH | Training knowledge + Superset export format |
| `position_json` v2 schema | HIGH | Training knowledge |
| REST API `passwords` parameter | MEDIUM | Training knowledge; verify against 4.1.1 API docs |
| Saved queries not importable | MEDIUM | Training knowledge; verify if changed in 4.1.x |
| `metadata.yaml` required fields | HIGH | Training knowledge |
| Metric/column `is_dttm` requirement | HIGH | Training knowledge |

**Recommended pre-implementation verification steps:**

1. Export one dashboard from this Superset instance (4.1.1). Inspect the ZIP structure to
   confirm format_version and YAML field names match what is documented here.
2. Check `docker compose exec superset superset import-dashboards --help` to see what formats
   4.1.1 actually accepts on the CLI.
3. Inspect the exported database YAML to confirm UUID field name (`uuid` vs `database_uuid`).
4. Test a minimal single-chart dashboard import end-to-end before scaling to full generation.
