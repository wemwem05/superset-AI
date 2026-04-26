# Superset Dashboard JSON Export/Import Format

**Project:** Superset 4.1.1 on Docker Compose
**Researched:** 2026-03-26
**Overall confidence:** HIGH (based on Superset source code knowledge through August 2025 cutoff; format is stable across 3.x and 4.x)

---

## 1. Overview: How Superset Exports Work

Superset does NOT export a single JSON file. It exports a **ZIP archive** (`.zip`) containing a structured directory tree of YAML files. This is the v1 import/export format introduced in Superset ~1.3 and is the only supported format in 4.x.

The v0 format (a single JSON blob with `__Dashboard__` keys) was removed. Any guide describing a single JSON file is describing the old, deprecated format. Do not use it.

The ZIP archive structure is:

```
dashboard_export_YYYYMMDDTHHMMSS/
  metadata.yaml
  dashboards/
    my_dashboard_title.yaml
  charts/
    chart_name_1.yaml
    chart_name_2.yaml
    ...
  datasets/
    database_name/
      table_name.yaml
      ...
  databases/
    database_name.yaml
    ...
```

Every file in the ZIP is YAML, not JSON. The import endpoint accepts either the ZIP or (for datasets only) a plain YAML file. For dashboards, the ZIP is mandatory.

---

## 2. File-by-File Structure

### 2.1 `metadata.yaml`

At the root of the ZIP. Identifies the export version and type.

```yaml
version: 1.0.0
type: Dashboard
timestamp: '2024-01-15T10:30:00+00:00'
```

`version: 1.0.0` is the string Superset checks to decide which importer class to invoke. This exact string is required. `type` must be one of: `Dashboard`, `Chart`, `Dataset`, `Database`.

### 2.2 `dashboards/<slug>.yaml`

The dashboard descriptor. Example of a complete, minimal valid dashboard:

```yaml
dashboard_title: My Sales Dashboard
description: null
css: ''
slug: my-sales-dashboard
uuid: 550e8400-e29b-41d4-a716-446655440000
published: true
certified_by: null
certification_details: null
position:
  DASHBOARD_VERSION_KEY: 'v2'
  ROOT_ID:
    children:
      - GRID_ID
    id: ROOT_ID
    type: ROOT
  GRID_ID:
    children:
      - ROW-abc123
    id: GRID_ID
    type: GRID
  ROW-abc123:
    children:
      - CHART-def456
    id: ROW-abc123
    meta:
      background: BACKGROUND_TRANSPARENT
    type: ROW
  CHART-def456:
    children: []
    id: CHART-def456
    meta:
      chartId: 1          # referenced by chart YAML uuid, not integer
      height: 50
      sliceName: Revenue by Month
      uuid: 7a3f2b10-1234-5678-abcd-000000000001
      width: 6
    type: CHART
metadata:
  native_filter_configuration: []
  chart_configuration: {}
  color_scheme: ''
  expanded_slices: {}
  filter_scopes: {}
  label_colors: {}
  refresh_frequency: 0
  remote_id: null
  timed_refresh_immune_slices: []
  version: '1.0.0'
```

### 2.3 `charts/<chart_name>.yaml`

One file per chart. Example of a bar chart:

```yaml
slice_name: Revenue by Month
viz_type: bar
description: null
certified_by: null
certification_details: null
uuid: 7a3f2b10-1234-5678-abcd-000000000001
dataset_uuid: a1b2c3d4-0000-0000-0000-111111111111
params: >
  {
    "adhoc_filters": [],
    "annotation_layers": [],
    "bottom_margin": "auto",
    "color_scheme": "supersetColors",
    "columns": [],
    "contribution": false,
    "groupby": ["month"],
    "label_colors": {},
    "limit": 10000,
    "metrics": [
      {
        "aggregate": "SUM",
        "column": {"column_name": "revenue", "type": "NUMERIC"},
        "expressionType": "SIMPLE",
        "label": "SUM(revenue)"
      }
    ],
    "order_bars": false,
    "rich_tooltip": true,
    "row_limit": 10000,
    "show_bar_value": false,
    "show_legend": true,
    "stacked_style": "stack",
    "time_range": "No filter",
    "viz_type": "bar",
    "x_axis_format": "smart_date",
    "y_axis_format": "SMART_NUMBER"
  }
cache_timeout: null
perm: null
schema_perm: null
```

Key fields:
- `uuid` — must match what the dashboard's position map references in `meta.uuid`
- `dataset_uuid` — must match the UUID of a dataset file in the same ZIP
- `params` — a JSON string (not a YAML object) containing all chart visualization parameters
- `viz_type` — the chart type identifier string

### 2.4 `datasets/<database_name>/<table_name>.yaml`

```yaml
table_name: sales_data
main_dttm_col: order_date
description: null
default_endpoint: null
offset: 0
cache_timeout: null
schema: public
sql: null
params: null
template_params: null
filter_select_enabled: false
fetch_values_predicate: null
extra: null
uuid: a1b2c3d4-0000-0000-0000-111111111111
metrics:
  - metric_name: revenue_sum
    verbose_name: Total Revenue
    metric_type: sum
    expression: SUM(revenue)
    description: null
    d3format: null
    currency: null
    extra: '{}'
    warning_text: null
    uuid: bbbbbbbb-0000-0000-0000-000000000001
columns:
  - column_name: order_date
    verbose_name: Order Date
    is_dttm: true
    is_active: true
    type: TIMESTAMP WITHOUT TIME ZONE
    advanced_data_type: null
    groupby: true
    filterable: true
    expression: null
    description: null
    extra: '{}'
    uuid: cccccccc-0000-0000-0000-000000000001
  - column_name: revenue
    verbose_name: Revenue
    is_dttm: false
    is_active: true
    type: NUMERIC
    advanced_data_type: null
    groupby: false
    filterable: true
    expression: null
    description: null
    extra: '{}'
    uuid: cccccccc-0000-0000-0000-000000000002
database_uuid: dddddddd-0000-0000-0000-000000000001
```

The `database_uuid` ties this dataset to a `databases/` file in the same ZIP.

### 2.5 `databases/<database_name>.yaml`

```yaml
database_name: My Production DB
sqlalchemy_uri: postgresql+psycopg2://user:XXXXXXXXXX@host:5432/dbname
cache_timeout: null
expose_in_sqllab: true
allow_run_async: true
allow_ctas: false
allow_cvas: false
allow_dml: false
force_ctas_schema: null
allow_file_upload: false
extra: >
  {
    "allows_virtual_table_explore": true,
    "metadata_params": {},
    "engine_params": {},
    "schemas_allowed_for_file_upload": []
  }
uuid: dddddddd-0000-0000-0000-000000000001
```

CRITICAL: The `sqlalchemy_uri` in an export contains the actual password. On export from a live instance, Superset redacts this to `XXXXXXXXXX`. On import, if the database already exists (matched by UUID), Superset uses the existing connection — it does NOT overwrite the URI with `XXXXXXXXXX`. If the database does NOT exist, you must provide a real URI.

---

## 3. Required vs Optional Fields

### Dashboard YAML — Required
- `dashboard_title` (string)
- `uuid` (UUID string)
- `position` (object — the layout tree)
- `position.DASHBOARD_VERSION_KEY` = `'v2'`
- `position.ROOT_ID` with `type: ROOT`
- `position.GRID_ID` with `type: GRID`
- `metadata` (object — can be empty `{}` but must exist)

### Dashboard YAML — Optional but Recommended
- `slug` — enables stable URL `/superset/dashboard/<slug>/`
- `published` — defaults to `false`; set `true` for visible dashboards
- `description`
- `css` — custom per-dashboard CSS string

### Chart YAML — Required
- `slice_name` (string)
- `viz_type` (string)
- `uuid` (UUID string)
- `dataset_uuid` (UUID string — must match a dataset file)
- `params` (JSON string)

### Dataset YAML — Required
- `table_name` (string)
- `uuid` (UUID string)
- `database_uuid` (UUID string — must match a database file)
- `columns` (array — can be empty but must be present)
- `metrics` (array — can be empty but must be present)

### Database YAML — Required
- `database_name` (string)
- `sqlalchemy_uri` (string)
- `uuid` (UUID string)

---

## 4. The Position / Layout System

The `position` field in the dashboard YAML is a flat dictionary (not a tree) where each key is a component ID. The tree structure is encoded via `children` arrays.

### Component Types

| type | Purpose | Required meta fields |
|------|---------|----------------------|
| `ROOT` | Single root node | none |
| `GRID` | Top-level grid container | none |
| `ROW` | Horizontal row | `background` |
| `CHART` | A chart panel | `chartId`, `height`, `width`, `sliceName`, `uuid` |
| `HEADER` | Text header element | `text`, `headerSize` |
| `MARKDOWN` | Markdown text box | `code`, `height`, `width` |
| `DIVIDER` | Horizontal divider | none |
| `TABS` | Tab container | none |
| `TAB` | Individual tab | `text`, `defaultText` |
| `COLUMN` | Column within row | `background`, `width` |

### Grid Sizing

Superset uses a 12-column grid. `width` values on CHART/COLUMN/MARKDOWN are integers 1–12. A full-width chart is `width: 12`. Two side-by-side charts are `width: 6` each. `height` is in "grid units" (approximately 4px each). Typical chart heights: 50 (small), 75 (medium), 100 (large).

### Example: Two Charts Side by Side

```yaml
position:
  DASHBOARD_VERSION_KEY: 'v2'
  ROOT_ID:
    children: [GRID_ID]
    id: ROOT_ID
    type: ROOT
  GRID_ID:
    children: [ROW-row1]
    id: GRID_ID
    type: GRID
  ROW-row1:
    children: [CHART-chart1, CHART-chart2]
    id: ROW-row1
    meta:
      background: BACKGROUND_TRANSPARENT
    type: ROW
  CHART-chart1:
    children: []
    id: CHART-chart1
    meta:
      chartId: 0             # ignored at import time; uuid is authoritative
      height: 50
      sliceName: Revenue Trend
      uuid: 7a3f2b10-1234-5678-abcd-000000000001
      width: 6
    type: CHART
  CHART-chart2:
    children: []
    id: CHART-chart2
    meta:
      chartId: 0
      height: 50
      sliceName: Orders by Region
      uuid: 7a3f2b10-1234-5678-abcd-000000000002
      width: 6
    type: CHART
```

Note: `chartId` is populated by Superset after import based on the `uuid` match. When generating JSON, set it to `0` or omit it — Superset resolves the real database ID from `uuid`.

---

## 5. UUID Strategy

UUIDs are the primary key for deduplication and cross-file references. The UUID system governs what happens on re-import:

- If a UUID already exists in the database, Superset **updates** (overwrites) the existing record.
- If a UUID does not exist, Superset **creates** a new record.

### Rules for Generated Dashboards

1. Generate all UUIDs using UUID v4 (random). Never reuse UUIDs across different logical objects.
2. The `database_uuid` in a dataset file must match exactly one database file's `uuid`.
3. The `dataset_uuid` in a chart file must match exactly one dataset file's `uuid`.
4. The `uuid` in a chart file's `meta` block inside the dashboard position tree must match the chart file's top-level `uuid`.
5. Do NOT reference database UUIDs that already exist in the target Superset instance unless you want to update that database record.

### Database UUID Handling (Critical for AI Generation)

When generating dashboards for import into an existing Superset instance where a database connection already exists:

**Option A — Include database file in ZIP with the real UUID of the existing database.** Superset will match by UUID and update (or no-op if nothing changed). The `sqlalchemy_uri` in the file will be ignored for existing connections.

**Option B — Omit the databases/ directory entirely and reference a database by UUID only.** This does NOT work — Superset validates that all referenced UUIDs resolve within the ZIP or existing records. If the database UUID is referenced in a dataset and the database does not exist in the ZIP, the import fails unless Superset can find that UUID in the metadata DB.

**Recommended approach:** Export the target database from the running Superset instance first, extract its UUID, and include that database YAML verbatim in generated ZIPs.

---

## 6. Import Process

### 6.1 UI Import (Superset 4.x)

1. Navigate to **Dashboards** list page.
2. Click the top-right menu (three dots or "Import" button).
3. Select **Import dashboards**.
4. Upload the `.zip` file.
5. If the ZIP contains a database with a masked URI (`XXXXXXXXXX`), the UI shows a dialog asking for the real password for each database.
6. Click **Import**.

The UI import calls `POST /api/v1/dashboard/import/` with multipart form data (`file` field = the ZIP).

### 6.2 API Import

```bash
curl -X POST http://localhost:8088/api/v1/dashboard/import/ \
  -H "Authorization: Bearer <token>" \
  -F "formData=@dashboard_export.zip" \
  -F "overwrite=true"
```

The `overwrite=true` flag tells Superset to overwrite existing objects with matching UUIDs. Without it, the import fails if any UUID already exists.

### 6.3 CLI Import

```bash
# Inside the superset container:
superset import-dashboards --path /path/to/export.zip
```

Or via Docker Compose:
```bash
docker compose exec superset superset import-dashboards --path /app/exports/dashboard.zip
```

The CLI command maps to the same v1 importer internally.

### 6.4 Authentication for API Import

```bash
# Step 1: Get access token
curl -X POST http://localhost:8088/api/v1/security/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin","provider":"db","refresh":true}'
# Returns: {"access_token": "...", "refresh_token": "..."}

# Step 2: Get CSRF token
curl -X GET http://localhost:8088/api/v1/security/csrf_token/ \
  -H "Authorization: Bearer <access_token>"
# Returns: {"result": "<csrf_token>"}

# Step 3: Import
curl -X POST http://localhost:8088/api/v1/dashboard/import/ \
  -H "Authorization: Bearer <access_token>" \
  -H "X-CSRFToken: <csrf_token>" \
  -F "formData=@export.zip" \
  -F "overwrite=true"
```

---

## 7. `params` Field in Charts

The `params` field is a **JSON string** (not a YAML object). It contains the full chart visualization configuration and varies significantly by `viz_type`. Below are the most common viz types and their key params.

### Common `viz_type` values in 4.x

| viz_type | Chart Name |
|----------|-----------|
| `echarts_timeseries_line` | Line Chart (ECharts) |
| `echarts_timeseries_bar` | Bar Chart (ECharts, vertical) |
| `echarts_timeseries_area` | Area Chart (ECharts) |
| `echarts_area` | Area Chart (legacy) |
| `bar` | Bar Chart (legacy NVD3) |
| `line` | Line Chart (legacy NVD3) |
| `pie` | Pie Chart |
| `echarts_pie` | Pie Chart (ECharts) |
| `big_number` | Big Number (single KPI) |
| `big_number_total` | Big Number with no trendline |
| `table` | Data Table |
| `pivot_table_v2` | Pivot Table |
| `dist_bar` | Distribution Bar |
| `box_plot` | Box Plot |
| `bubble` | Bubble Chart |
| `funnel` | Funnel Chart |
| `gauge_chart` | Gauge |
| `mixed_timeseries` | Mixed Chart (line + bar) |
| `treemap_v2` | Treemap |
| `sunburst_v2` | Sunburst |
| `heatmap` | Heatmap |
| `country_map` | Country Map |
| `world_map` | World Map |

### Minimal params for `big_number_total`

```json
{
  "viz_type": "big_number_total",
  "metric": {
    "aggregate": "COUNT",
    "column": null,
    "expressionType": "SQL",
    "label": "COUNT(*)",
    "sqlExpression": "COUNT(*)"
  },
  "adhoc_filters": [],
  "header_font_size": 0.4,
  "subheader": "",
  "subheader_font_size": 0.15,
  "time_range": "No filter",
  "row_limit": 10000
}
```

### Minimal params for `echarts_timeseries_line`

```json
{
  "viz_type": "echarts_timeseries_line",
  "x_axis": "order_date",
  "metrics": [
    {
      "aggregate": "SUM",
      "column": {"column_name": "revenue", "type": "NUMERIC"},
      "expressionType": "SIMPLE",
      "label": "SUM(revenue)"
    }
  ],
  "groupby": [],
  "adhoc_filters": [],
  "time_range": "No filter",
  "row_limit": 10000,
  "x_axis_time_format": "smart_date",
  "time_grain_sqla": "P1D",
  "rich_tooltip": true,
  "show_legend": true,
  "zoomable": false
}
```

### Minimal params for `table`

```json
{
  "viz_type": "table",
  "query_mode": "aggregate",
  "groupby": ["region", "category"],
  "metrics": [
    {
      "aggregate": "SUM",
      "column": {"column_name": "revenue", "type": "NUMERIC"},
      "expressionType": "SIMPLE",
      "label": "SUM(revenue)"
    }
  ],
  "all_columns": [],
  "adhoc_filters": [],
  "time_range": "No filter",
  "row_limit": 10000,
  "order_by_cols": [],
  "show_cell_bars": true,
  "align_pn": false,
  "color_pn": true,
  "include_search": false,
  "page_length": 0
}
```

---

## 8. Native Filters

Native filters (the filter bar on the left/top of dashboards) are configured in the dashboard YAML under `metadata.native_filter_configuration`. This is an array.

```yaml
metadata:
  native_filter_configuration:
    - id: NATIVE_FILTER-abc123
      name: Date Range
      filterType: filter_time
      targets:
        - datasetId: null
          column: null
      defaultDataMask:
        filterState:
          value: null
      controlValues:
        defaultToFirstItem: false
      cascadeParentIds: []
      scope:
        rootPath: [ROOT_ID]
        excluded: []
      type: NATIVE_FILTER
    - id: NATIVE_FILTER-def456
      name: Region
      filterType: filter_select
      targets:
        - datasetId: 1        # resolved from uuid after import
          column:
            name: region
      defaultDataMask:
        filterState:
          value: null
      controlValues:
        enableEmptyFilter: false
        defaultToFirstItem: false
        multiSelect: true
        searchAllOptions: false
        inverseSelection: false
      cascadeParentIds: []
      scope:
        rootPath: [ROOT_ID]
        excluded: []
      type: NATIVE_FILTER
```

The `datasetId` integer in filter targets is resolved by Superset after import from the dataset UUID. When generating manually, set it to `null` or `0`; Superset will not auto-resolve it. This is a known limitation: **native filters with dataset-scoped targets require manual reconfiguration after import if generated from scratch**.

---

## 9. Version-Specific Notes for 4.1.1

### ECharts is the default
In Superset 4.x, the primary chart library is ECharts. The legacy NVD3 charts (`bar`, `line`, `area`) still exist but new charts default to `echarts_timeseries_*` variants. Generated dashboards should prefer ECharts viz types.

### `DASHBOARD_NATIVE_FILTERS` feature flag
This project has `DASHBOARD_NATIVE_FILTERS: True` in `superset_config.py`. This enables the filter bar. Native filter configuration in dashboard YAML is fully supported.

### `DASHBOARD_CROSS_FILTERS`
Also enabled in this project. Cross-filter configuration lives in `metadata.chart_configuration`:

```yaml
metadata:
  chart_configuration:
    "7a3f2b10-1234-5678-abcd-000000000001":
      id: "7a3f2b10-1234-5678-abcd-000000000001"
      crossFilters:
        scope:
          rootPath: [ROOT_ID]
          excluded: []
        chartsInScope: []
```

### Removed in 4.x
- `filter_scopes` (legacy filter system) — ignored by 4.x importer; use `native_filter_configuration` instead.
- The v0 import format (single JSON blob) — completely removed.

### UUID validation tightened in 4.x
Superset 4.x validates UUID format strictly. Must be RFC 4122 compliant (8-4-4-4-12 hex groups). Passing non-UUID strings as identifiers will fail validation with a 400 error.

---

## 10. Common Pitfalls When Creating Dashboard JSON Manually

### Pitfall 1: Treating the export as a single JSON file
The v1 format is a ZIP of YAML files. Generating a single `.json` file and uploading it will fail with "Invalid file format".

### Pitfall 2: Using JSON instead of YAML
The individual files must be YAML. While JSON is valid YAML, the importer reads YAML parsers and some fields (like `params`) are expected as JSON strings embedded within YAML — not nested objects.

### Pitfall 3: UUID mismatches
The chart's `uuid` in `charts/my_chart.yaml` must exactly match the `meta.uuid` value in the dashboard's `position` block. A single typo causes "chart not found" errors with no helpful message.

### Pitfall 4: The `params` field must be a JSON string, not a YAML object
```yaml
# WRONG — will fail or produce empty chart
params:
  viz_type: bar
  metrics:
    - ...

# CORRECT — JSON encoded as a YAML string scalar
params: >
  {"viz_type": "bar", "metrics": [...]}
```

### Pitfall 5: Missing `DASHBOARD_VERSION_KEY` in position
The position object must contain `DASHBOARD_VERSION_KEY: 'v2'` as a top-level key. Without it, the layout renderer falls back to v1 behavior (no grid) and charts may not display.

### Pitfall 6: Database URI handling
If you include a `databases/` YAML with `sqlalchemy_uri: XXXXXXXXXX`, Superset cannot create a new connection. Either include the real URI or ensure the database already exists in the target instance with that UUID.

### Pitfall 7: chart `width` values that don't add up to 12
All charts in a ROW must have `width` values summing to 12 (or less). Values over 12 in a single row cause rendering overlap. Superset does not validate this at import time — it silently renders incorrectly.

### Pitfall 8: `metrics` as column references vs. SQL
Metric objects in `params` must be one of two `expressionType` values:
- `"SIMPLE"` — uses `aggregate` + `column` fields
- `"SQL"` — uses `sqlExpression` field

Mixing them (e.g., providing both `aggregate` and `sqlExpression`) produces unpredictable results.

### Pitfall 9: `time_range` format
The `time_range` field in chart params must be a recognized string. Valid values include:
- `"No filter"`
- `"Last day"`
- `"Last week"`
- `"Last month"`
- `"Last quarter"`
- `"Last year"`
- `"Last 7 days"`
- `"Last 30 days"`
- `"Last 90 days"`
- `"Last 365 days"`
- Custom: `"2024-01-01 : 2024-12-31"` (ISO dates separated by ` : `)

Invalid `time_range` strings cause the chart to fail to load with a 400 from the query engine.

### Pitfall 10: `is_dttm` column flag must be set correctly
In dataset columns, `is_dttm: true` must be set for date/timestamp columns. Charts that use time-series features require at least one `is_dttm` column. If this is absent, the time column selector in charts will be empty.

### Pitfall 11: File naming inside the ZIP
The directory structure inside the ZIP must match the exact layout: `dashboards/`, `charts/`, `datasets/`, `databases/`. File names within those directories are not validated (any `.yaml` extension works), but the directories themselves must exist.

### Pitfall 12: Import without `overwrite=true` on re-import
If you import the same dashboard twice (same UUIDs), the second import fails without `overwrite=true`. The UI checkbox says "Overwrite existing files" — it must be checked. The API requires `overwrite=true` in the form data.

---

## 11. Recommended ZIP Generation Workflow (for Claude)

When Claude generates a Superset dashboard ZIP:

1. Generate all UUIDs deterministically (UUID v4, random, not sequential).
2. Create the following files:
   - `metadata.yaml` — version + type header
   - `databases/<db_name>.yaml` — one file per referenced database
   - `datasets/<db_name>/<table_name>.yaml` — one file per referenced table
   - `charts/<chart_slug>.yaml` — one file per chart (use sanitized `slice_name` as filename)
   - `dashboards/<dashboard_slug>.yaml` — one dashboard file
3. In the dashboard YAML, populate `position` with a valid ROOT → GRID → ROW → CHART tree.
4. Ensure every chart UUID appears in both the chart YAML and the dashboard position's `meta.uuid`.
5. Set `published: true` if the dashboard should be immediately visible.
6. Package all files into a ZIP preserving the directory structure.
7. Name the ZIP `dashboard_export_<YYYYMMDDTHHMMSS>.zip` (convention, not validated).

The Python snippet to create such a ZIP:
```python
import zipfile, io

def create_superset_zip(files: dict[str, str]) -> bytes:
    """files = {relative_path: yaml_content}"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()
```

---

## 12. Obtaining the Database UUID from a Running Instance

Since the database UUID is needed to link datasets, and hardcoding a wrong UUID causes import failure, the safest approach is to query the running Superset API:

```bash
# Get list of databases with their UUIDs
curl -X GET http://localhost:8088/api/v1/database/ \
  -H "Authorization: Bearer <token>" \
  | python3 -m json.tool | grep -E '"id"|"database_name"|"uuid"'
```

The API returns UUIDs in the response. Alternatively, export an existing dataset from the UI to get the database YAML with the correct UUID, then hardcode that UUID in generated datasets.

---

## 13. Confidence Assessment

| Topic | Confidence | Basis |
|-------|------------|-------|
| ZIP + YAML format | HIGH | Stable since Superset 1.3; confirmed in 3.x/4.x source |
| `metadata.yaml` structure | HIGH | Documented in source importer code |
| Dashboard position system | HIGH | Well-documented in community; unchanged in 4.x |
| Chart `params` field contents | MEDIUM | Varies by viz_type; complex params may need trial-and-error |
| Native filter configuration | MEDIUM | Works but `datasetId` linkage post-import requires verification |
| ECharts viz_type names | HIGH | Confirmed stable in 4.x |
| Database UUID matching behavior | HIGH | Core to import logic, well-documented in Superset issues |
| 4.1.1-specific changes | MEDIUM | No major format changes from 4.0 to 4.1; specific changelog not verifiable via web |

---

## 14. Sources

All findings are from training knowledge based on:
- Apache Superset source code (commands/dashboard/importers/v1/) as of 4.x line
- Apache Superset GitHub issues and PRs discussing import/export (through August 2025 cutoff)
- Superset community Slack and GitHub Discussions patterns
- Official Superset documentation on importing/exporting

**NOTE:** Web access was unavailable during this research session. Findings are based on training data through August 2025. For any breaking changes in patch releases after that date, inspect the running container:
```bash
docker compose exec superset python -c "import superset; print(superset.__version__)"
```
And review the changelog at: https://github.com/apache/superset/blob/4.1.1/CHANGELOG/4.1.1.md
