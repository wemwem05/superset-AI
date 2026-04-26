# Superset Chart Types and Visualization Capabilities

**Project:** Apache Superset 4.1.1 (self-hosted, Docker Compose)
**Researched:** 2026-03-26
**Overall confidence:** MEDIUM
**Note on sources:** Web and Bash tools are restricted in this environment.
Findings below draw from (a) the Superset 4.x codebase as known through
training data (cutoff Aug 2025), (b) the project's local config files, and
(c) the official Apache Superset GitHub repository structure. All items are
confidence-labelled. Claims marked HIGH have strong cross-source support;
MEDIUM require verification against a running instance; LOW are inferences.

---

## 1. Chart Type Taxonomy

Superset 4.x ships two distinct visualization stacks:

| Stack | Plugin prefix | When introduced | Notes |
|-------|--------------|-----------------|-------|
| **Legacy (Python-backed)** | none (uses `viz.py`) | Original | Being phased out; still present in 4.1 |
| **ECharts / Apache plugin** | `echarts_*` | 1.x → complete by 3.x | Recommended for new dashboards |

In the UI, both stacks are available in the chart gallery under
**"+ Chart"**. The `viz_type` field in a chart's `params` JSON determines
which renderer is invoked.

---

## 2. Complete viz_type Reference

### 2.1 Tabular / Data Table Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Table | `table` | HIGH |
| Pivot Table v2 | `pivot_table_v2` | HIGH |
| Time-series Table | `time_table` | MEDIUM |

**Required fields for `table`:**
- `metrics` — at least one aggregate (e.g., `COUNT(*)`, `SUM(amount)`)
- `groupby` — zero or more dimension columns
- Optional: `filters`, `row_limit` (default 1000), `order_by_cols`, `include_search`

**Key options:** `page_length`, `show_totals`, `conditional_formatting`
(cell-level color rules based on value thresholds).

---

### 2.2 Bar / Column Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Bar Chart (ECharts) | `echarts_bar` | HIGH |
| Bar Chart (legacy) | `dist_bar` | HIGH |
| Horizontal Bar (legacy) | `horizontal_bar` | MEDIUM |

**Required fields for `echarts_bar`:**
- `x_axis` — dimension column for x-axis
- `metrics` — one or more aggregates
- Optional: `groupby` (creates grouped/stacked series), `stack` (boolean),
  `y_axis_format`, `rich_tooltip`, `x_ticks_layout`

---

### 2.3 Line / Area Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Line Chart (ECharts) | `echarts_timeseries_line` | HIGH |
| Area Chart (ECharts) | `echarts_area` | HIGH |
| Smooth Line | `echarts_timeseries_smooth` | MEDIUM |
| Step Line | `echarts_timeseries_step` | MEDIUM |
| Scatter (ECharts timeseries) | `echarts_timeseries_scatter` | MEDIUM |
| Mixed Chart (bar + line) | `mixed_timeseries` | HIGH |

**Required fields for `echarts_timeseries_line`:**
- `x_axis` — datetime or ordinal column
- `metrics` — one or more aggregates
- `granularity_sqla` — time grain (day, week, month, etc.)
- Optional: `groupby`, `time_range`, `annotation_layers`

---

### 2.4 Pie / Donut Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Pie Chart (ECharts) | `echarts_pie` | HIGH |
| Funnel Chart | `echarts_funnel` | HIGH |
| Gauge Chart | `echarts_gauge` | HIGH |
| Rose / Nightingale | `echarts_nightingale` | MEDIUM |
| Radar Chart | `echarts_radar` | HIGH |

**Required fields for `echarts_pie`:**
- `groupby` — dimension that defines slices
- `metric` — single aggregate for slice size
- Optional: `donut` (boolean), `show_labels`, `label_type`

---

### 2.5 Scatter / Bubble Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Scatter Plot (ECharts) | `echarts_timeseries_scatter` | MEDIUM |
| Bubble Chart | `bubble_v2` | MEDIUM |

**Required fields for `bubble_v2`:**
- `x` — metric for x-axis
- `y` — metric for y-axis
- `size` — metric for bubble size
- `series` — dimension grouping

---

### 2.6 Map / Geo Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Country Map | `country_map` | HIGH |
| World Map | `world_map` | HIGH |
| Deck.gl Scatter | `deck_scatter` | HIGH |
| Deck.gl Grid | `deck_grid` | HIGH |
| Deck.gl Hex | `deck_hex` | HIGH |
| Deck.gl Arc | `deck_arc` | MEDIUM |
| Deck.gl Path | `deck_path` | MEDIUM |
| Deck.gl Polygon | `deck_polygon` | MEDIUM |
| Deck.gl 3D Scatter | `deck_3d` | MEDIUM |
| Deck.gl GeoJSON | `deck_geojson` | MEDIUM |
| Mapbox Choropleth | `mapbox` | MEDIUM (requires API key) |

**Notes on geo charts:**
- `country_map` and `world_map` require a column that maps to ISO country/
  region codes. No API key needed — uses built-in GeoJSON boundaries.
- Deck.gl charts require latitude/longitude columns.
- `mapbox` requires `MAPBOX_API_KEY` in config — already supported in
  this project's `superset_config.py`.
- The project's config has `MAPBOX_API_KEY = os.environ.get("MAPBOX_API_KEY", "")`
  so setting the env var enables Mapbox without code changes.

---

### 2.7 Heatmaps

| Display Name | viz_type | Confidence |
|---|---|---|
| Heatmap (ECharts) | `echarts_heatmap` | HIGH |
| Calendar Heatmap | `cal_heatmap` | MEDIUM |
| Heatmap (legacy) | `heatmap` | MEDIUM |

**Required fields for `echarts_heatmap`:**
- `x_axis` — column for x categories
- `groupby` — column for y categories
- `metric` — single aggregate for cell color intensity

---

### 2.8 Box Plots / Statistical Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Box Plot (ECharts) | `echarts_boxplot` | HIGH |
| Histogram | `histogram` | HIGH |

**Required fields for `echarts_boxplot`:**
- `columns` — numeric columns to compute distribution stats on
- `groupby` — optional grouping dimension

---

### 2.9 KPI / Summary Cards

| Display Name | viz_type | Confidence |
|---|---|---|
| Big Number | `big_number` | HIGH |
| Big Number with Trendline | `big_number_total` | HIGH |

**Required fields for `big_number`:**
- `metric` — single aggregate
- Optional: `subheader`, `time_format`, `y_axis_format`, compare_lag,
  compare_suffix (for % change vs previous period)

`big_number_total` adds a sparkline trendline using the time dimension.
These are the most effective summary statistics for a demo dashboard.

---

### 2.10 Tree / Hierarchy Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Treemap (ECharts) | `echarts_treemap_v2` | HIGH |
| Sunburst | `echarts_sunburst` | MEDIUM |
| Sankey Diagram | `echarts_sankey` | HIGH |

---

### 2.11 Network / Flow Charts

| Display Name | viz_type | Confidence |
|---|---|---|
| Network Graph | `network` | MEDIUM |
| Sankey | `echarts_sankey` | HIGH |

---

### 2.12 Financial / Candlestick

| Display Name | viz_type | Confidence |
|---|---|---|
| Candlestick | `echarts_timeseries_candlestick` | MEDIUM |

---

### 2.13 Other / Utility

| Display Name | viz_type | Confidence |
|---|---|---|
| Word Cloud | `word_cloud` | HIGH |
| Waterfall Chart | `waterfall` | HIGH |
| Chord Diagram | `chord` | MEDIUM |
| Force-directed Graph | `graph_chart` | MEDIUM |

---

## 3. Dashboard Layout System

### 3.1 Grid Model

Superset dashboards use a **24-column Bootstrap-style grid**. Each component
occupies a rectangle defined by `(x, y, w, h)` where:
- `x` — left offset in grid units (0–23)
- `y` — top offset in grid units
- `w` — width in grid units
- `h` — height in grid units (roughly 50px per unit)

The JSON structure of a dashboard's `position_json` is a nested tree:

```json
{
  "DASHBOARD_VERSION_KEY": "v2",
  "ROOT_ID": {
    "type": "ROOT",
    "id": "ROOT_ID",
    "children": ["GRID_ID"]
  },
  "GRID_ID": {
    "type": "GRID",
    "id": "GRID_ID",
    "children": ["ROW-uuid1", "ROW-uuid2"]
  },
  "ROW-uuid1": {
    "type": "ROW",
    "id": "ROW-uuid1",
    "meta": { "background": "BACKGROUND_TRANSPARENT" },
    "children": ["CHART-uuid1", "CHART-uuid2"]
  },
  "CHART-uuid1": {
    "type": "CHART",
    "id": "CHART-uuid1",
    "meta": {
      "chartId": 42,
      "width": 8,
      "height": 50
    },
    "children": []
  }
}
```

**Confidence: HIGH** — this structure is stable across 2.x–4.x and is used
by the export/import API.

### 3.2 Dashboard Component Types

| Type | Purpose | Notes |
|------|---------|-------|
| `ROOT` | Top-level container | Always present, always id `ROOT_ID` |
| `GRID` | The main layout canvas | Always child of ROOT |
| `ROW` | Horizontal row | Flex container for charts side-by-side |
| `COLUMN` | Vertical stack inside a row | Optional sub-division |
| `CHART` | Rendered chart | References `chartId` (slice ID) |
| `HEADER` | Section heading text | `meta.text` |
| `MARKDOWN` | Freeform HTML/Markdown | `meta.code` |
| `TABS` | Tab container | Children are `TAB` nodes |
| `TAB` | Individual tab | Contains rows/charts |
| `DIVIDER` | Horizontal rule separator | Visual only |

### 3.3 Tabs

Tabs allow a single dashboard to host multiple "pages":

```json
"TABS-uuid": {
  "type": "TABS",
  "id": "TABS-uuid",
  "children": ["TAB-uuid1", "TAB-uuid2"]
},
"TAB-uuid1": {
  "type": "TAB",
  "id": "TAB-uuid1",
  "meta": { "text": "Overview", "defaultText": "Tab 1" },
  "children": ["ROW-uuid3"]
}
```

Tabs are rendered as horizontal tabs at the top of the dashboard area.
Nested tabs are supported but not recommended (UX confusion).

**Confidence: HIGH**

---

## 4. Native Filters (Dashboard Filters)

This project has `DASHBOARD_NATIVE_FILTERS: True` and
`DASHBOARD_CROSS_FILTERS: True` enabled — both are active.

### 4.1 Filter Types

| Filter Type | filter_type | What it filters | Notes |
|---|---|---|---|
| Value (Select) | `filter_select` | Exact match on a dimension column | Supports multi-select, search, cascade |
| Numerical Range | `filter_range` | Min/max on a numeric column | Renders as dual-handle slider |
| Time Range | `filter_time` | Time column range | Renders as calendar picker |
| Time Column | `filter_timecolumn` | Which column to use as time | Dataset-level |
| Time Grain | `filter_timegrain` | Granularity (day/week/month) | Works with time column filter |
| Custom SQL | `filter_custom_sql` | WHERE clause via SQL snippet | Requires ENABLE_TEMPLATE_PROCESSING |

**Confidence: HIGH** — these types are unchanged since 2.x.

### 4.2 Filter Configuration Fields

Each native filter has:
- `id` — unique string (e.g., `"NATIVE_FILTER-xyz"`)
- `name` — display label shown above the filter control
- `filterType` — one of the types above
- `targets` — array of `{ datasetId, column: { name } }` objects
- `scope` — which charts in the dashboard are affected
  - `rootPath: ["ROOT_ID"]` + `excluded: [chart_id_1]` pattern
- `defaultDataMask` — initial filter value (optional)
- `cascadeParentIds` — for hierarchical filters (e.g., Country → City)

### 4.3 Cross-Filtering

With `DASHBOARD_CROSS_FILTERS: True`, clicking a data point on a chart that
supports cross-filtering automatically filters all other compatible charts.
Charts that emit cross-filter events: table, bar, line, pie, scatter, and
most ECharts-based plugins.

Charts explicitly exclude themselves from being affected by cross-filters
via their `scope` config.

**Confidence: MEDIUM** — behavior verified from docs but exact chart
compatibility list may have changed in 4.1.

---

## 5. Advanced Features

### 5.1 Annotations

Annotation layers are supported on time-series charts
(`echarts_timeseries_line`, `echarts_area`, `mixed_timeseries`, etc.).

**Layer types:**
- **Event annotations** — vertical marker lines at specific timestamps
  (e.g., product launches, incidents)
- **Interval annotations** — shaded time bands between two timestamps
- **Formula annotations** — constant horizontal lines (y = value)
- **Time-series annotations** — overlay data from a second dataset

Each chart's `params` includes an `annotation_layers` array.

**Confidence: HIGH**

### 5.2 Drill-Down / Drill-Through

Superset 4.x supports two types of drill interaction:

1. **Drill to Detail** — right-click a data point opens a modal with raw
   rows from the underlying dataset filtered to that data point.
   Feature flag: `DRILL_TO_DETAIL` (disabled by default in 4.1; can be
   enabled in `FEATURE_FLAGS`).

2. **Drill By** — allows users to pivot the groupby dimension on the fly
   without leaving the chart. Available on ECharts-based charts.
   Feature flag: `DRILL_BY`.

**Confidence: MEDIUM** — flags exist in 4.1 source but default state
should be verified.

### 5.3 Jinja Template Processing

`ENABLE_TEMPLATE_PROCESSING: True` is already configured. This enables:
- `{{ current_user() }}` — inject the logged-in username into SQL
- `{{ filter_values('column') }}` — reference filter values in SQL
- `{{ url_param('param') }}` — read URL query params
- `{% set start, end = get_time_range('30 days ago', 'now') %}` — time macros

This is used for row-level security in virtual datasets and custom filter SQL.

### 5.4 Alert and Reports

`ALERT_REPORTS: True` is configured, and the celery beat schedule includes
`reports.scheduler`. This enables scheduled PDF/image exports of dashboards
sent via email or Slack webhook.

**Confidence: HIGH** — config is already in place.

---

## 6. Chart JSON Structure (params field)

The `params` field stored in the `slices` table is a JSON blob. Key fields:

```json
{
  "viz_type": "echarts_timeseries_line",
  "datasource": "12__table",
  "time_range": "Last 30 days",
  "granularity_sqla": "created_at",
  "time_grain_sqla": "P1D",
  "x_axis": "created_at",
  "metrics": [
    {
      "expressionType": "SIMPLE",
      "column": { "column_name": "revenue" },
      "aggregate": "SUM",
      "label": "SUM(revenue)"
    }
  ],
  "groupby": ["category"],
  "row_limit": 10000,
  "show_legend": true,
  "rich_tooltip": true,
  "y_axis_format": "SMART_NUMBER",
  "color_scheme": "supersetColors",
  "annotation_layers": []
}
```

**Metric expressionType values:**
- `"SIMPLE"` — column + aggregate (SUM, COUNT, AVG, MIN, MAX, COUNT_DISTINCT)
- `"SQL"` — raw SQL expression like `COUNT(DISTINCT user_id)`
- `"SAVED_METRIC"` — references a pre-defined metric from the dataset

**Confidence: HIGH** — this structure is stable and exported in dashboard
ZIP files.

---

## 7. What Makes a Good Demo Dashboard

A demo dashboard showcasing Superset 4.1.1 capabilities should:

### 7.1 Chart Variety Checklist

Include at least one of each type:
- [ ] `big_number` or `big_number_total` — KPI summary row at the top
- [ ] `echarts_timeseries_line` or `echarts_area` — trend over time
- [ ] `echarts_bar` — categorical comparison
- [ ] `echarts_pie` — distribution/proportion
- [ ] `table` with conditional formatting — detailed data + search
- [ ] `echarts_treemap_v2` or `echarts_sunburst` — hierarchical breakdown
- [ ] `country_map` or `world_map` — geographic distribution (no API key needed)
- [ ] `echarts_gauge` — single-metric progress indicator
- [ ] `histogram` or `echarts_boxplot` — statistical distribution

### 7.2 Layout Best Practices

```
Row 1: [big_number w=6] [big_number w=6] [big_number w=6] [big_number w=6]
Row 2: [line/area chart w=16] [pie chart w=8]
Row 3: [bar chart w=12] [treemap w=12]
Row 4: [table w=24, full width, paginated]
Tab 2: [map w=24]
Tab 3: [gauge w=8] [histogram w=16]
```

### 7.3 Filter Setup for a Demo

Recommended native filters:
1. **Time Range filter** (`filter_time`) — controls all time-based charts
2. **Category select** (`filter_select`) — multi-select, drives cross-filter
3. **Numeric range** (`filter_range`) — optional, for quantitative slicing

Enable cross-filtering so that clicking a bar segment filters the table and
line chart — this is the most impressive live demo interaction.

### 7.4 Recommended Color Scheme

`"color_scheme": "supersetColors"` is the default 10-color categorical
palette. For a cleaner demo: `"color_scheme": "airbnb"` or
`"color_scheme": "google"`.

For sequential palettes (heatmaps, choropleths): `"linear_color_scheme":
"blue_white_yellow"` or `"linear_color_scheme": "oranges"`.

### 7.5 Sample Dataset Recommendation

Use Superset's built-in example data (loaded via `superset load_examples`)
which includes:
- `birth_names` — demographic name frequency data (good for bar/line/map)
- `energy_usage` — time-series energy consumption (good for line/area)
- `flights` — origin/destination pairs (good for Deck.gl arc maps)
- `world_health` — country-level health metrics (good for world_map)
- `FCC 2018 Survey` — survey data (good for histograms, scatter)

Load command: `docker compose exec superset superset load_examples`

**Confidence: HIGH** — load_examples has been stable across versions.

---

## 8. Dashboard Import/Export Format

Dashboards can be exported as ZIP files (Superset 1.3+, stable in 4.x).
The ZIP contains:

```
dashboard_export_YYYYMMDD_HHMMSS/
  dashboards/
    My_Dashboard.yaml           # dashboard metadata + position_json
  charts/
    chart_name_1.yaml           # per-chart params
    chart_name_2.yaml
  datasets/
    db_name/
      table_name.yaml           # dataset config + metrics + columns
  databases/
    database_name.yaml          # connection config (no passwords)
```

This format is useful for programmatically creating dashboards: generate
YAML files and import via the API (`POST /api/v1/dashboard/import`).

**Confidence: HIGH** — ZIP import/export is a first-class 4.x feature.

---

## 9. REST API for Chart/Dashboard Creation

Superset 4.x exposes a full REST API at `/api/v1/`:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/chart/` | POST | Create a new chart (slice) |
| `/api/v1/chart/{id}` | PUT | Update chart params |
| `/api/v1/dashboard/` | POST | Create dashboard |
| `/api/v1/dashboard/{id}` | PUT | Update layout/metadata |
| `/api/v1/dashboard/import` | POST | Import ZIP |
| `/api/v1/dashboard/export` | GET | Export ZIP |
| `/api/v1/dataset/` | GET | List available datasets |
| `/api/v1/explore/form_data` | POST | Save explore form state |

Authentication: JWT Bearer token (obtain via `POST /api/v1/security/login`).

**For Claude-generated dashboards:** the most reliable approach is:
1. Create datasets via API (or use existing ones)
2. Create each chart via `POST /api/v1/chart/` with full `params` JSON
3. Build `position_json` programmatically
4. Create dashboard via `POST /api/v1/dashboard/` referencing chart IDs

**Confidence: HIGH** — this API pattern is stable in 4.x.

---

## 10. Known Pitfalls for Claude-Generated Dashboards

### Pitfall 1: datasource field format
`"datasource"` must be `"{id}__table"` not just a table name. The dataset
ID must be looked up via `GET /api/v1/dataset/` first.

### Pitfall 2: metric JSON vs string
Some viz_types accept metrics as plain strings (`"COUNT(*)"`) in legacy
charts, but ECharts plugins require the full metric object with
`expressionType`, `column`, `aggregate`, `label`. Mixing formats causes
silent empty results.

### Pitfall 3: time_range format
Valid values: `"Last 7 days"`, `"Last 30 days"`, `"Last year"`,
`"No filter"`, or ISO range `"2024-01-01T00:00:00 : 2024-12-31T23:59:59"`.
The colon-space separator is required for ISO ranges.

### Pitfall 4: position_json width arithmetic
Chart widths in a ROW must sum to 24 (or less). Superset renders them
left-to-right but does not wrap; overflow is clipped.

### Pitfall 5: filter scope vs chart IDs
Filter `scope` uses chart IDs (integers from `slices.id`), not the position
JSON UUIDs. Must be set after charts are created and IDs are known.

### Pitfall 6: ECharts vs legacy viz_type naming
`dist_bar` (legacy) and `echarts_bar` are both present and appear similar
in the gallery. Prefer `echarts_*` variants — they have more options and
better cross-filter support. Legacy variants may be removed in a future
major version.

### Pitfall 7: MAPBOX_API_KEY optional
Deck.gl charts (scatter, grid, hex) work without a Mapbox key using the
default basemap. Only `mapbox` (choropleth) strictly requires the key.
Country/world maps need no key at all.

---

## 11. Confidence Assessment Summary

| Area | Confidence | Basis |
|------|------------|-------|
| viz_type identifiers (ECharts) | HIGH | Stable since 3.x, confirmed naming conventions |
| viz_type identifiers (legacy) | MEDIUM | May have deprecated entries in 4.1 |
| Dashboard position_json schema | HIGH | Unchanged 2.x–4.x, used in export format |
| Native filter types | HIGH | Stable, feature flags already in project config |
| Cross-filtering behavior | MEDIUM | Config present; per-chart support list unverified |
| Deck.gl chart availability | MEDIUM | Depends on whether deck.gl deps bundled in custom image |
| Drill-down feature flags | LOW | Default state in 4.1.1 not verified without live instance |
| API endpoints | HIGH | Documented and stable in 4.x |
| Example datasets | HIGH | load_examples unchanged across versions |

---

## 12. Gaps to Verify Against Running Instance

1. Run `docker compose exec superset superset load_examples` to confirm
   example datasets load successfully with the custom image.
2. Navigate to `+ Chart` in the UI to get the authoritative chart type list
   for exactly this image build.
3. Check `GET /api/v1/chart/viz_types` (if available in 4.1) for the
   machine-readable list of enabled viz_types.
4. Verify `DRILL_TO_DETAIL` and `DRILL_BY` feature flags are available
   by checking Settings > Feature Flags in the UI.
5. Test Deck.gl charts — the custom image `martian322/superset:latest`
   may or may not include the deck.gl npm bundle.
