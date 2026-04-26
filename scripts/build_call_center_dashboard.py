#!/usr/bin/env python3
"""
Build Call Center Analytics dashboard from sales_amo_leads_calls dataset (ID: 5).

Tab 1 — Overview: funnel KPIs + daily volume/CR trends
Tab 2 — Breakdowns: device, country, age, hour×dow heatmaps
Tab 3 — Lead Type: per-flag CR to purchase time series

Also adds calculated columns (age_group) and saved metrics to the dataset.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI, SUPERSET_URL, USERNAME, PASSWORD

DATASET_ID = 5
DATASET_UID = "5__table"
DASHBOARD_TITLE = "Call Center Analytics"

TEMPORAL_FILTER = {
    "clause": "WHERE",
    "subject": "lead_time",
    "operator": "TEMPORAL_RANGE",
    "comparator": "No filter",
    "expressionType": "SIMPLE",
}

# ── Reusable metric SQL ──────────────────────────────────────────
M_LEADS = "COUNT(lead_id)"
M_CALLED = "SUM(CASE WHEN calls_count > 0 THEN 1 ELSE 0 END)"
M_ANSWERED = "SUM(CASE WHEN answered_calls_count > 0 THEN 1 ELSE 0 END)"
M_15MIN = "SUM(CASE WHEN first_call_time - lead_time < '15 minutes'::interval THEN 1 ELSE 0 END)"
M_PURCHASES = "SUM(CASE WHEN purchase THEN 1 ELSE 0 END)"
M_REVENUE = "SUM(purchase_price)"
M_CR_CALL = f"{M_CALLED}::float / NULLIF({M_LEADS}, 0)"
M_CR_ANSWERED = f"{M_ANSWERED}::float / NULLIF({M_LEADS}, 0)"
M_CR_15MIN = f"{M_15MIN}::float / NULLIF({M_LEADS}, 0)"
M_CR_PURCHASE = f"{M_PURCHASES}::float / NULLIF({M_LEADS}, 0)"

AGE_GROUP_SQL = (
    "CASE "
    "WHEN user_age < 18 THEN '1-<18' "
    "WHEN user_age < 25 THEN '2-18-24' "
    "WHEN user_age < 35 THEN '3-25-34' "
    "WHEN user_age < 45 THEN '4-35-44' "
    "ELSE '5-45+' END"
)


def sql_metric(expr, label):
    return {
        "expressionType": "SQL",
        "sqlExpression": expr,
        "hasCustomLabel": True,
        "label": label,
    }


def create_chart(api, dashboard_id, name, viz_type, params):
    params.setdefault("datasource", DATASET_UID)
    params.setdefault("viz_type", viz_type)
    params.setdefault("adhoc_filters", [TEMPORAL_FILTER])

    payload = {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": DATASET_ID,
        "datasource_type": "table",
        "params": json.dumps(params),
        "dashboards": [dashboard_id],
    }
    result = api.post("/api/v1/chart/", payload)
    chart_id = result["id"]
    print(f"  [+] Chart #{chart_id}: {name}", file=sys.stderr)
    return chart_id


# ── Dataset modifications ────────────────────────────────────────

def update_dataset(api):
    """Add calculated columns and saved metrics to the dataset."""
    data = api.get(f"/api/v1/dataset/{DATASET_ID}")
    result = data["result"]

    existing_cols = result.get("columns", [])
    existing_metrics = result.get("metrics", [])
    col_names = {c["column_name"] for c in existing_cols}
    metric_names = {m["metric_name"] for m in existing_metrics}

    # Calculated columns to add
    new_calc_cols = {
        "age_group": AGE_GROUP_SQL,
    }

    # Saved metrics to add
    new_metrics = {
        "total_leads":    ("Total Leads",      M_LEADS),
        "leads_called":   ("Leads Called",      M_CALLED),
        "leads_answered": ("Leads Answered",    M_ANSWERED),
        "leads_15min":    ("Called in 15 min",  M_15MIN),
        "purchases":      ("Purchases",         M_PURCHASES),
        "total_revenue":  ("Total Revenue",     M_REVENUE),
        "cr_to_call":     ("CR to Call",        M_CR_CALL),
        "cr_to_answered": ("CR to Answered",    M_CR_ANSWERED),
        "cr_to_15min":    ("CR to 15 min",      M_CR_15MIN),
        "cr_to_purchase": ("CR to Purchase",    M_CR_PURCHASE),
    }

    # Build columns payload (existing + new)
    cols_payload = []
    for c in existing_cols:
        col = {
            "column_name": c["column_name"],
            "filterable": c.get("filterable", True),
            "groupby": c.get("groupby", True),
            "is_dttm": c.get("is_dttm", False),
        }
        if c.get("id"):
            col["id"] = c["id"]
        if c.get("expression"):
            col["expression"] = c["expression"]
        if c.get("type"):
            col["type"] = c["type"]
        cols_payload.append(col)

    added_cols = 0
    for name, expr in new_calc_cols.items():
        if name not in col_names:
            cols_payload.append({
                "column_name": name,
                "expression": expr,
                "type": "VARCHAR(50)",
                "filterable": True,
                "groupby": True,
                "is_dttm": False,
            })
            added_cols += 1
            print(f"  [+] Column: {name}", file=sys.stderr)

    # Build metrics payload (existing + new)
    metrics_payload = []
    for m in existing_metrics:
        met = {
            "metric_name": m["metric_name"],
            "expression": m.get("expression", ""),
            "verbose_name": m.get("verbose_name", ""),
        }
        if m.get("id"):
            met["id"] = m["id"]
        metrics_payload.append(met)

    added_metrics = 0
    for mname, (verbose, expr) in new_metrics.items():
        if mname not in metric_names:
            metrics_payload.append({
                "metric_name": mname,
                "verbose_name": verbose,
                "expression": expr,
            })
            added_metrics += 1
            print(f"  [+] Metric: {mname}", file=sys.stderr)

    if added_cols == 0 and added_metrics == 0:
        print("  Dataset already up to date", file=sys.stderr)
        return

    update = {}
    if added_cols > 0:
        update["columns"] = cols_payload
    if added_metrics > 0:
        update["metrics"] = metrics_payload

    api.put(f"/api/v1/dataset/{DATASET_ID}", update)
    print(f"  Dataset updated: +{added_cols} columns, +{added_metrics} metrics", file=sys.stderr)


# ── Chart creation ───────────────────────────────────────────────

def create_charts(api, dash_id):
    """Create all charts and return dict of name -> chart_id."""
    c = {}

    # ── TAB 1: Overview ──────────────────────────────────────────

    # Row 1: Absolute KPIs
    c["kpi_leads"] = create_chart(api, dash_id, "Calls: Total Leads", "big_number_total", {
        "metric": sql_metric(M_LEADS, "Total Leads"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    })
    c["kpi_called"] = create_chart(api, dash_id, "Calls: Leads Called", "big_number_total", {
        "metric": sql_metric(M_CALLED, "Leads Called"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    })
    c["kpi_answered"] = create_chart(api, dash_id, "Calls: Leads Answered", "big_number_total", {
        "metric": sql_metric(M_ANSWERED, "Leads Answered"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    })
    c["kpi_15min"] = create_chart(api, dash_id, "Calls: Called in 15 min", "big_number_total", {
        "metric": sql_metric(M_15MIN, "Called in 15 min"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    })
    c["kpi_purchases"] = create_chart(api, dash_id, "Calls: Purchases", "big_number_total", {
        "metric": sql_metric(M_PURCHASES, "Purchases"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    })
    c["kpi_revenue"] = create_chart(api, dash_id, "Calls: Revenue", "big_number_total", {
        "metric": sql_metric(M_REVENUE, "Revenue"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    })

    # Row 2: Conversion rate KPIs
    c["kpi_cr_call"] = create_chart(api, dash_id, "Calls: CR to Call", "big_number_total", {
        "metric": sql_metric(M_CR_CALL, "CR to Call"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": ".1%",
    })
    c["kpi_cr_answered"] = create_chart(api, dash_id, "Calls: CR to Answered", "big_number_total", {
        "metric": sql_metric(M_CR_ANSWERED, "CR to Answered"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": ".1%",
    })
    c["kpi_cr_15min"] = create_chart(api, dash_id, "Calls: CR to 15 min", "big_number_total", {
        "metric": sql_metric(M_CR_15MIN, "CR to 15 min"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": ".1%",
    })
    c["kpi_cr_purchase"] = create_chart(api, dash_id, "Calls: CR to Purchase", "big_number_total", {
        "metric": sql_metric(M_CR_PURCHASE, "CR to Purchase"),
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": ".1%",
    })

    # Row 3: Daily funnel volumes
    c["ts_volumes"] = create_chart(api, dash_id, "Calls: Daily Funnel Volumes", "echarts_timeseries_line", {
        "x_axis": "lead_time",
        "time_grain_sqla": "P1D",
        "metrics": [
            sql_metric(M_LEADS, "Leads"),
            sql_metric(M_CALLED, "Called"),
            sql_metric(M_ANSWERED, "Answered"),
            sql_metric(M_15MIN, "Called 15 min"),
            sql_metric(M_PURCHASES, "Purchases"),
        ],
        "groupby": [],
        "row_limit": 10000,
        "color_scheme": "supersetColors",
        "markerEnabled": True,
        "show_value": False,
        "zoomable": True,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "y_axis_format": "SMART_NUMBER",
        "truncateXAxis": True,
        "comparison_type": "values",
    })

    # Row 4: Daily conversion rates
    c["ts_crs"] = create_chart(api, dash_id, "Calls: Daily Conversion Rates", "echarts_timeseries_line", {
        "x_axis": "lead_time",
        "time_grain_sqla": "P1D",
        "metrics": [
            sql_metric(M_CR_CALL, "CR to Call"),
            sql_metric(M_CR_ANSWERED, "CR to Answered"),
            sql_metric(M_CR_15MIN, "CR to 15 min"),
            sql_metric(M_CR_PURCHASE, "CR to Purchase"),
        ],
        "groupby": [],
        "row_limit": 10000,
        "color_scheme": "supersetColors",
        "markerEnabled": True,
        "show_value": False,
        "zoomable": True,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "y_axis_format": ".1%",
        "truncateXAxis": True,
        "comparison_type": "values",
    })

    # ── TAB 2: Breakdowns ────────────────────────────────────────

    breakdown_metrics = [
        sql_metric(M_LEADS, "Leads"),
        sql_metric(M_CR_CALL, "CR Call"),
        sql_metric(M_CR_ANSWERED, "CR Answered"),
        sql_metric(M_CR_15MIN, "CR 15 min"),
        sql_metric(M_CR_PURCHASE, "CR Purchase"),
        sql_metric(M_REVENUE, "Revenue"),
    ]

    breakdown_col_config = {
        "CR Call": {"d3NumberFormat": ".1%"},
        "CR Answered": {"d3NumberFormat": ".1%"},
        "CR 15 min": {"d3NumberFormat": ".1%"},
        "CR Purchase": {"d3NumberFormat": ".1%"},
        "Revenue": {"d3NumberFormat": ",.0f"},
    }

    c["tbl_device"] = create_chart(api, dash_id, "Calls: by Device Type", "table", {
        "query_mode": "aggregate",
        "groupby": ["device_type"],
        "metrics": breakdown_metrics,
        "order_desc": True,
        "row_limit": 50,
        "show_totals": True,
        "show_cell_bars": True,
        "color_pn": True,
        "page_length": 20,
        "column_config": breakdown_col_config,
    })

    c["tbl_country"] = create_chart(api, dash_id, "Calls: by Country", "table", {
        "query_mode": "aggregate",
        "groupby": ["country"],
        "metrics": breakdown_metrics,
        "order_desc": True,
        "row_limit": 50,
        "show_totals": True,
        "show_cell_bars": True,
        "color_pn": True,
        "page_length": 20,
        "column_config": breakdown_col_config,
    })

    c["tbl_age"] = create_chart(api, dash_id, "Calls: by Age Group", "table", {
        "query_mode": "aggregate",
        "groupby": ["age_group"],
        "metrics": breakdown_metrics,
        "order_desc": True,
        "row_limit": 50,
        "show_totals": True,
        "show_cell_bars": True,
        "color_pn": True,
        "page_length": 20,
        "column_config": breakdown_col_config,
    })

    c["heatmap_leads"] = create_chart(api, dash_id, "Calls: Leads by Hour & Day of Week", "heatmap", {
        "all_columns_x": {
            "expressionType": "SQL",
            "label": "Day of Week",
            "sqlExpression": "EXTRACT(ISODOW FROM lead_time)::int || '-' || TO_CHAR(lead_time, 'Dy')",
        },
        "all_columns_y": {
            "expressionType": "SQL",
            "label": "Hour",
            "sqlExpression": "LPAD(EXTRACT(HOUR FROM lead_time)::text, 2, '0') || ':00'",
        },
        "metric": sql_metric(M_LEADS, "Leads"),
        "linear_color_scheme": "superset_seq_1",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_values": True,
        "normalize_across": "heatmap",
    })

    c["heatmap_cr"] = create_chart(api, dash_id, "Calls: CR Answered by Hour & Day of Week", "heatmap", {
        "all_columns_x": {
            "expressionType": "SQL",
            "label": "Day of Week",
            "sqlExpression": "EXTRACT(ISODOW FROM lead_time)::int || '-' || TO_CHAR(lead_time, 'Dy')",
        },
        "all_columns_y": {
            "expressionType": "SQL",
            "label": "Hour",
            "sqlExpression": "LPAD(EXTRACT(HOUR FROM lead_time)::text, 2, '0') || ':00'",
        },
        "metric": sql_metric(M_CR_ANSWERED, "CR Answered"),
        "linear_color_scheme": "superset_seq_1",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_values": True,
        "normalize_across": "heatmap",
        "value_format": ".1%",
    })

    # ── TAB 3: Lead Type Analysis ────────────────────────────────

    lead_flags = [
        ("is_new", "New"),
        ("is_comeback", "Comeback"),
        ("is_guest", "Guest"),
        ("is_acquisition", "Acquisition"),
        ("is_ref", "Referral"),
    ]

    for col, label in lead_flags:
        c[f"ts_{col}"] = create_chart(api, dash_id, f"Calls: CR to Purchase — {label}", "echarts_timeseries_line", {
            "x_axis": "lead_time",
            "time_grain_sqla": "P1D",
            "metrics": [sql_metric(M_CR_PURCHASE, "CR to Purchase")],
            "groupby": [col],
            "row_limit": 10000,
            "color_scheme": "supersetColors",
            "markerEnabled": True,
            "show_value": False,
            "zoomable": True,
            "show_legend": True,
            "legendType": "scroll",
            "legendOrientation": "top",
            "x_axis_time_format": "smart_date",
            "rich_tooltip": True,
            "y_axis_format": ".1%",
            "truncateXAxis": True,
            "comparison_type": "values",
        })

    return c


# ── Layout ───────────────────────────────────────────────────────

def build_layout(c):
    """Build 3-tab position_json."""
    tabs = [
        {
            "title": "Overview",
            "rows": [
                # Row 1: 6 absolute KPIs
                [(c["kpi_leads"], 2, 18), (c["kpi_called"], 2, 18), (c["kpi_answered"], 2, 18),
                 (c["kpi_15min"], 2, 18), (c["kpi_purchases"], 2, 18), (c["kpi_revenue"], 2, 18)],
                # Row 2: 4 CR KPIs
                [(c["kpi_cr_call"], 3, 18), (c["kpi_cr_answered"], 3, 18),
                 (c["kpi_cr_15min"], 3, 18), (c["kpi_cr_purchase"], 3, 18)],
                # Row 3: Daily volumes
                [(c["ts_volumes"], 12, 50)],
                # Row 4: Daily CRs
                [(c["ts_crs"], 12, 50)],
            ],
        },
        {
            "title": "Breakdowns",
            "rows": [
                [(c["tbl_device"], 12, 50)],
                [(c["tbl_country"], 6, 50), (c["tbl_age"], 6, 50)],
                [(c["heatmap_leads"], 6, 70), (c["heatmap_cr"], 6, 70)],
            ],
        },
        {
            "title": "Lead Type Analysis",
            "rows": [
                [(c["ts_is_new"], 6, 50), (c["ts_is_comeback"], 6, 50)],
                [(c["ts_is_guest"], 6, 50), (c["ts_is_acquisition"], 6, 50)],
                [(c["ts_is_ref"], 6, 50)],
            ],
        },
    ]

    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": DASHBOARD_TITLE}},
        "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"]},
        "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": ["TABS-1"]},
    }

    tabs_id = "TABS-1"
    position[tabs_id] = {
        "id": tabs_id,
        "type": "TABS",
        "children": [],
        "parents": ["ROOT_ID", "GRID_ID"],
    }

    row_counter = 0

    for tab_idx, tab_def in enumerate(tabs, start=1):
        tab_id = f"TAB-{tab_idx}"
        position[tabs_id]["children"].append(tab_id)
        position[tab_id] = {
            "id": tab_id,
            "type": "TAB",
            "children": [],
            "parents": ["ROOT_ID", "GRID_ID", tabs_id],
            "meta": {"text": tab_def["title"], "defaultText": f"Tab {tab_idx}"},
        }

        for row_charts in tab_def["rows"]:
            row_counter += 1
            row_id = f"ROW-CC{row_counter}"
            row_children = []

            for (chart_id, width, height) in row_charts:
                chart_key = f"CHART-{chart_id}"
                row_children.append(chart_key)
                position[chart_key] = {
                    "id": chart_key,
                    "type": "CHART",
                    "children": [],
                    "parents": ["ROOT_ID", "GRID_ID", tabs_id, tab_id, row_id],
                    "meta": {
                        "chartId": chart_id,
                        "width": width,
                        "height": height,
                        "sliceName": "",
                    },
                }

            position[row_id] = {
                "id": row_id,
                "type": "ROW",
                "children": row_children,
                "parents": ["ROOT_ID", "GRID_ID", tabs_id, tab_id],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            position[tab_id]["children"].append(row_id)

    return position


# ── Native filters ───────────────────────────────────────────────

def build_filters():
    """Build native filter configuration."""
    filters_def = [
        ("country", "Country"),
        ("device_type", "Device Type"),
        ("is_new", "Is New"),
        ("is_comeback", "Is Comeback"),
        ("is_guest", "Is Guest"),
        ("is_acquisition", "Is Acquisition"),
        ("is_ref", "Is Referral"),
    ]

    native_filters = []
    for i, (col, label) in enumerate(filters_def):
        filter_id = f"NATIVE_FILTER-CC{i+1}"
        native_filters.append({
            "id": filter_id,
            "controlValues": {
                "enableEmptyFilter": False,
                "defaultToFirstItem": False,
                "multiSelect": True,
                "searchAllOptions": False,
                "inverseSelection": False,
            },
            "name": label,
            "filterType": "filter_select",
            "targets": [{"datasetId": DATASET_ID, "column": {"name": col}}],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "type": "NATIVE_FILTER",
        })

    return native_filters


# ── Main ─────────────────────────────────────────────────────────

def main():
    print("=" * 60, file=sys.stderr)
    print("Call Center Analytics Dashboard", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    # Step 1: Update dataset
    print("\n[1/5] Updating dataset with calculated columns & metrics...", file=sys.stderr)
    update_dataset(api)

    # Step 2: Create empty dashboard
    print("\n[2/5] Creating dashboard...", file=sys.stderr)
    result = api.post("/api/v1/dashboard/", {
        "dashboard_title": DASHBOARD_TITLE,
        "published": True,
    })
    dash_id = result["id"]
    print(f"  Dashboard #{dash_id}: {DASHBOARD_TITLE}", file=sys.stderr)

    # Step 3: Create all charts
    print("\n[3/5] Creating charts...", file=sys.stderr)
    chart_ids = create_charts(api, dash_id)
    print(f"\n  Created {len(chart_ids)} charts", file=sys.stderr)

    # Step 4: Build and apply layout
    print("\n[4/5] Building layout...", file=sys.stderr)
    position = build_layout(chart_ids)
    native_filters = build_filters()

    json_metadata = {
        "native_filter_configuration": native_filters,
        "default_filters": "{}",
        "timed_refresh_immune_slices": [],
        "expanded_slices": {},
        "refresh_frequency": 0,
        "chart_configuration": {},
        "color_scheme": "",
        "label_colors": {},
    }

    api.put(f"/api/v1/dashboard/{dash_id}", {
        "position_json": json.dumps(position),
        "json_metadata": json.dumps(json_metadata),
    })
    print(f"  Layout applied with 3 tabs and {len(native_filters)} filters", file=sys.stderr)

    # Step 5: Summary
    print("\n[5/5] Done!", file=sys.stderr)
    url = f"{SUPERSET_URL}/superset/dashboard/{dash_id}/"
    print(f"\n  Dashboard URL: {url}", file=sys.stderr)

    summary = {
        "dashboard_id": dash_id,
        "url": url,
        "tabs": ["Overview", "Breakdowns", "Lead Type Analysis"],
        "charts": {k: v for k, v in chart_ids.items()},
        "filters": [f["name"] for f in native_filters],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
