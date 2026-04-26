#!/usr/bin/env python3
"""
Restructure the Extra Sales dashboard (ID: 2) into 6 tabs with new charts.

Tabs:
  1. Overview & KPIs
  2. Sales Trends
  3. Product Analytics
  4. Geography & Segments
  5. Refunds & Health
  6. Raw Data

Creates ~19 new charts and reorganizes all 12 existing ones.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI, SUPERSET_URL, USERNAME, PASSWORD, build_auto_layout

DASHBOARD_ID = 2
DATASET_ID = 1
DATASET_UID = "1__table"

TEMPORAL_PASSTHROUGH = {
    "clause": "WHERE",
    "subject": "purchase_date",
    "operator": "TEMPORAL_RANGE",
    "comparator": "No filter",
    "expressionType": "SIMPLE",
}

# ── Existing chart IDs ────────────────────────────────────────────
EXISTING = {
    "gauge": 1,          # Extra Revenue Target (200M)
    "total_sales": 2,    # Extra Total Sales
    "total_revenue": 3,  # Extra Total Revenue
    "aov": 4,            # Extra AOV
    "rev_by_days": 6,    # Extra Revenue by Days
    "rev_by_products": 7,# Extra Revenue by Products (pie)
    "rev_by_cities": 8,  # Extra Revenue by Cities
    "rev_by_user_type": 9,# Extra Revenue by User Type (pie)
    "trend_monthly": 10, # Extra Sales Trend (Monthly)
    "top_refunded": 11,  # Extra Top Refunded Products
    "data_table": 12,    # Extra Sales Data
    "trend_weekly": 25,  # Extra Sales Trend (Weekly)
}


def create_chart(api, name, viz_type, params):
    """Create a chart and return its ID."""
    params.setdefault("datasource", DATASET_UID)
    params.setdefault("viz_type", viz_type)
    params.setdefault("adhoc_filters", [TEMPORAL_PASSTHROUGH])

    payload = {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": DATASET_ID,
        "datasource_type": "table",
        "params": json.dumps(params),
        "dashboards": [DASHBOARD_ID],
    }
    result = api.post("/api/v1/chart/", payload)
    chart_id = result["id"]
    print(f"  [+] Chart #{chart_id}: {name} ({viz_type})", file=sys.stderr)
    return chart_id


def update_gauge_to_usd(api):
    """Update gauge from 200M local to 50,000 USD."""
    params_patch = {
        "metric": {
            "aggregate": "SUM",
            "column": {"column_name": "price_usd", "type": "INTEGER"},
            "expressionType": "SIMPLE",
            "label": "Revenue USD",
        },
        "max_val": 50000,
        "intervals": [20000, 35000, 50000],
    }
    # Read current params
    data = api.get(f"/api/v1/chart/{EXISTING['gauge']}")
    current = json.loads(data["result"]["params"])
    current.update(params_patch)
    api.put(f"/api/v1/chart/{EXISTING['gauge']}", {
        "slice_name": "Extra Revenue Target (50K USD)",
        "params": json.dumps(current),
    })
    print(f"  [~] Chart #{EXISTING['gauge']}: gauge updated to 50K USD", file=sys.stderr)


def create_new_charts(api):
    """Create all new charts and return dict of name -> chart_id."""
    new = {}

    # ── TAB 1: Overview ──────────────────────────────────────────

    new["kpi_revenue_usd"] = create_chart(api, "Extra Total Revenue (USD)", "big_number_total", {
        "metric": {
            "aggregate": "SUM",
            "column": {"column_name": "price_usd", "type": "INTEGER"},
            "expressionType": "SIMPLE",
            "label": "Revenue USD",
        },
        "subheader": "total revenue (USD)",
        "header_font_size": 0.2,
        "subheader_font_size": 0.15,
        "y_axis_format": ",.0f",
        "currency_format": {"symbol": "USD"},
    })

    new["kpi_refund_rate"] = create_chart(api, "Extra Refund Rate", "big_number_total", {
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "SUM(CASE WHEN refund THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0)",
            "hasCustomLabel": True,
            "label": "Refund Rate",
        },
        "subheader": "refund rate",
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": ".1%",
    })

    new["rev_by_country_pie"] = create_chart(api, "Extra Revenue by Country", "pie", {
        "groupby": ["country"],
        "metric": {
            "aggregate": "SUM",
            "column": {"column_name": "price_usd", "type": "INTEGER"},
            "expressionType": "SIMPLE",
            "label": "Revenue USD",
        },
        "row_limit": 20,
        "sort_by_metric": True,
        "color_scheme": "supersetColors",
        "show_labels": True,
        "labels_outside": True,
        "label_line": True,
        "label_type": "key_percent",
        "number_format": "SMART_NUMBER",
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "outerRadius": 70,
        "donut": False,
    })

    # ── TAB 2: Sales Trends ──────────────────────────────────────

    new["sales_count_weekly"] = create_chart(api, "Extra Sales Count (Weekly)", "echarts_area", {
        "x_axis": "purchase_date",
        "time_grain_sqla": "P1W",
        "metrics": [{"aggregate": "COUNT", "column": {"column_name": "price", "type": "DOUBLE PRECISION"}, "expressionType": "SIMPLE", "label": "Sales Count"}],
        "groupby": ["product"],
        "row_limit": 10000,
        "truncate_metric": True,
        "show_empty_columns": True,
        "comparison_type": "values",
        "sort_series_type": "sum",
        "color_scheme": "supersetColors",
        "seriesType": "line",
        "opacity": 0.2,
        "show_value": True,
        "stack": "Stack",
        "only_total": True,
        "show_extra_controls": True,
        "markerEnabled": False,
        "zoomable": True,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "y_axis_format": "SMART_NUMBER",
        "truncateXAxis": True,
    })

    new["product_monthly_table"] = create_chart(api, "Extra Revenue by Product (Monthly)", "table", {
        "query_mode": "aggregate",
        "groupby": ["product"],
        "temporal_columns_lookup": {"purchase_date": True},
        "metrics": [
            {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "hasCustomLabel": True, "label": "Sales"},
            {"expressionType": "SQL", "sqlExpression": "SUM(price)", "hasCustomLabel": True, "label": "Revenue"},
            {"expressionType": "SQL", "sqlExpression": "SUM(price_usd)", "hasCustomLabel": True, "label": "Revenue USD"},
            {"expressionType": "SQL", "sqlExpression": "AVG(price)", "hasCustomLabel": True, "label": "AOV"},
        ],
        "order_by_cols": [],
        "row_limit": 50,
        "order_desc": True,
        "show_totals": True,
        "include_search": False,
        "show_cell_bars": True,
        "color_pn": True,
        "table_timestamp_format": "%Y-%m-%d",
        "page_length": 20,
        "column_config": {
            "Revenue": {"d3NumberFormat": ",.0f"},
            "Revenue USD": {"d3NumberFormat": ",.0f"},
            "AOV": {"d3NumberFormat": ",.0f"},
        },
    })

    new["heatmap_hour_day"] = create_chart(api, "Extra Sales by Hour & Day of Week", "heatmap", {
        "all_columns_x": {
            "expressionType": "SQL",
            "label": "Day of Week",
            "sqlExpression": "EXTRACT(ISODOW FROM purchase_time)::int || '-' || TO_CHAR(purchase_time, 'Dy')",
        },
        "all_columns_y": {
            "expressionType": "SQL",
            "label": "Hour",
            "sqlExpression": "LPAD(EXTRACT(HOUR FROM purchase_time)::text, 2, '0') || ':00'",
        },
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "COUNT(*)",
            "hasCustomLabel": True,
            "label": "Sales",
        },
        "linear_color_scheme": "superset_seq_1",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_values": True,
        "normalize_across": "heatmap",
    })

    # ── TAB 3: Product Analytics ─────────────────────────────────

    new["product_perf_table"] = create_chart(api, "Extra Product Performance", "table", {
        "query_mode": "aggregate",
        "groupby": ["product"],
        "metrics": [
            {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "hasCustomLabel": True, "label": "Sales"},
            {"expressionType": "SQL", "sqlExpression": "SUM(price)", "hasCustomLabel": True, "label": "Revenue"},
            {"expressionType": "SQL", "sqlExpression": "SUM(price_usd)", "hasCustomLabel": True, "label": "Revenue USD"},
            {"expressionType": "SQL", "sqlExpression": "AVG(price)", "hasCustomLabel": True, "label": "AOV"},
            {"expressionType": "SQL", "sqlExpression": "SUM(refund_amount)", "hasCustomLabel": True, "label": "Refunds"},
            {"expressionType": "SQL", "sqlExpression": "SUM(CASE WHEN refund THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0)", "hasCustomLabel": True, "label": "Refund Rate"},
        ],
        "order_by_cols": [],
        "row_limit": 50,
        "order_desc": True,
        "show_totals": True,
        "include_search": False,
        "show_cell_bars": True,
        "color_pn": True,
        "page_length": 20,
        "column_config": {
            "Revenue": {"d3NumberFormat": ",.0f"},
            "Revenue USD": {"d3NumberFormat": ",.0f"},
            "AOV": {"d3NumberFormat": ",.0f"},
            "Refunds": {"d3NumberFormat": ",.0f"},
            "Refund Rate": {"d3NumberFormat": ".1%"},
        },
    })

    new["product_rev_trend"] = create_chart(api, "Extra Product Revenue Trend", "echarts_timeseries_line", {
        "x_axis": "purchase_date",
        "time_grain_sqla": "P1W",
        "metrics": [{"aggregate": "SUM", "column": {"column_name": "price", "type": "DOUBLE PRECISION"}, "expressionType": "SIMPLE", "label": "Revenue"}],
        "groupby": ["product"],
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

    new["product_vol_trend"] = create_chart(api, "Extra Product Sales Volume Trend", "echarts_timeseries_line", {
        "x_axis": "purchase_date",
        "time_grain_sqla": "P1W",
        "metrics": [{"expressionType": "SQL", "sqlExpression": "COUNT(*)", "hasCustomLabel": True, "label": "Sales Count"}],
        "groupby": ["product"],
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

    new["product_usertype_heatmap"] = create_chart(api, "Extra Product x User Type", "heatmap", {
        "all_columns_x": {
            "expressionType": "SQL",
            "label": "Product",
            "sqlExpression": "product",
        },
        "all_columns_y": {
            "expressionType": "SQL",
            "label": "User Type",
            "sqlExpression": "user_type",
        },
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "COUNT(*)",
            "hasCustomLabel": True,
            "label": "Sales",
        },
        "linear_color_scheme": "superset_seq_1",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_values": True,
        "normalize_across": "heatmap",
    })

    new["product_country_bar"] = create_chart(api, "Extra Product Revenue by Country", "echarts_timeseries_bar", {
        "x_axis": "product",
        "x_axis_sort_asc": True,
        "x_axis_sort_series": "sum",
        "x_axis_sort_series_ascending": False,
        "metrics": [{"aggregate": "SUM", "column": {"column_name": "price_usd", "type": "INTEGER"}, "expressionType": "SIMPLE", "label": "Revenue USD"}],
        "groupby": ["country"],
        "row_limit": 50,
        "truncate_metric": True,
        "orientation": "vertical",
        "color_scheme": "supersetColors",
        "show_value": True,
        "stack": "Stack",
        "only_total": True,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "comparison_type": "values",
    })

    # ── TAB 4: Geography & Segments ──────────────────────────────

    new["rev_by_country_trend"] = create_chart(api, "Extra Revenue by Country (Monthly)", "echarts_timeseries_bar", {
        "x_axis": "purchase_date",
        "time_grain_sqla": "P1M",
        "metrics": [{"aggregate": "SUM", "column": {"column_name": "price_usd", "type": "INTEGER"}, "expressionType": "SIMPLE", "label": "Revenue USD"}],
        "groupby": ["country"],
        "row_limit": 10000,
        "truncate_metric": True,
        "orientation": "vertical",
        "color_scheme": "supersetColors",
        "show_value": True,
        "stack": "Stack",
        "only_total": True,
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

    new["usertype_rev_trend"] = create_chart(api, "Extra User Type Revenue Trend", "echarts_timeseries_line", {
        "x_axis": "purchase_date",
        "time_grain_sqla": "P1W",
        "metrics": [{"aggregate": "SUM", "column": {"column_name": "price", "type": "DOUBLE PRECISION"}, "expressionType": "SIMPLE", "label": "Revenue"}],
        "groupby": ["user_type"],
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

    new["city_product_table"] = create_chart(api, "Extra City x Product Sales", "table", {
        "query_mode": "aggregate",
        "groupby": ["user_city", "product"],
        "metrics": [
            {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "hasCustomLabel": True, "label": "Sales"},
            {"expressionType": "SQL", "sqlExpression": "SUM(price)", "hasCustomLabel": True, "label": "Revenue"},
        ],
        "order_by_cols": [],
        "row_limit": 100,
        "order_desc": True,
        "show_totals": True,
        "include_search": True,
        "show_cell_bars": True,
        "color_pn": True,
        "page_length": 20,
        "column_config": {
            "Revenue": {"d3NumberFormat": ",.0f"},
        },
    })

    new["top_cities_volume"] = create_chart(api, "Extra Top Cities by Sales Volume", "echarts_timeseries_bar", {
        "x_axis": "user_city",
        "x_axis_sort_asc": True,
        "x_axis_sort_series": "sum",
        "x_axis_sort_series_ascending": True,
        "metrics": [{"expressionType": "SQL", "sqlExpression": "COUNT(*)", "hasCustomLabel": True, "label": "Sales Count"}],
        "groupby": [],
        "row_limit": 20,
        "truncate_metric": True,
        "orientation": "horizontal",
        "color_scheme": "supersetColors",
        "show_value": True,
        "only_total": True,
        "show_legend": False,
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "comparison_type": "values",
    })

    # ── TAB 5: Refunds & Health ──────────────────────────────────

    new["kpi_refund_amount"] = create_chart(api, "Extra Total Refund Amount", "big_number_total", {
        "metric": {
            "aggregate": "SUM",
            "column": {"column_name": "refund_amount", "type": "DOUBLE PRECISION"},
            "expressionType": "SIMPLE",
            "label": "Refund Amount",
        },
        "subheader": "total refunded",
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": ",.0f",
    })

    new["kpi_refund_count"] = create_chart(api, "Extra Refund Count", "big_number_total", {
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "SUM(CASE WHEN refund THEN 1 ELSE 0 END)",
            "hasCustomLabel": True,
            "label": "Refund Count",
        },
        "subheader": "refunded orders",
        "header_font_size": 0.3,
        "subheader_font_size": 0.15,
        "y_axis_format": ",.0f",
    })

    new["refund_trend"] = create_chart(api, "Extra Refund Trend (Weekly)", "echarts_timeseries_line", {
        "x_axis": "purchase_date",
        "time_grain_sqla": "P1W",
        "metrics": [{"aggregate": "SUM", "column": {"column_name": "refund_amount", "type": "DOUBLE PRECISION"}, "expressionType": "SIMPLE", "label": "Refund Amount"}],
        "groupby": [],
        "row_limit": 10000,
        "color_scheme": "bnbColors",
        "markerEnabled": True,
        "show_value": True,
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

    new["refund_rate_by_product"] = create_chart(api, "Extra Refund Rate by Product", "echarts_timeseries_bar", {
        "x_axis": "product",
        "x_axis_sort_asc": True,
        "x_axis_sort_series": "name",
        "x_axis_sort_series_ascending": True,
        "metrics": [{
            "expressionType": "SQL",
            "sqlExpression": "SUM(CASE WHEN refund THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0)",
            "hasCustomLabel": True,
            "label": "Refund Rate",
        }],
        "groupby": [],
        "row_limit": 50,
        "truncate_metric": True,
        "orientation": "horizontal",
        "color_scheme": "bnbColors",
        "show_value": True,
        "only_total": True,
        "show_legend": False,
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "y_axis_format": ".1%",
        "comparison_type": "values",
    })

    new["refund_timing"] = create_chart(api, "Extra Refund Timing (Daily)", "echarts_timeseries_bar", {
        "x_axis": "refund_date",
        "time_grain_sqla": "P1D",
        "metrics": [{"expressionType": "SQL", "sqlExpression": "SUM(CASE WHEN refund THEN 1 ELSE 0 END)", "hasCustomLabel": True, "label": "Refunds"}],
        "groupby": [],
        "adhoc_filters": [
            TEMPORAL_PASSTHROUGH,
            {"clause": "WHERE", "expressionType": "SQL", "sqlExpression": "refund_date IS NOT NULL"},
        ],
        "row_limit": 10000,
        "truncate_metric": True,
        "orientation": "vertical",
        "color_scheme": "bnbColors",
        "show_value": False,
        "only_total": True,
        "zoomable": True,
        "show_legend": False,
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "y_axis_format": "SMART_NUMBER",
        "truncateXAxis": True,
        "comparison_type": "values",
    })

    return new


def build_layout(new_ids):
    """Build the complete 6-tab position_json."""
    E = EXISTING

    # Tab definitions: list of (title, rows)
    # Each row is a list of (chart_id, width, height)
    tabs = [
        {
            "title": "Overview & KPIs",
            "rows": [
                [(E["total_sales"], 3, 18), (E["total_revenue"], 3, 18), (new_ids["kpi_revenue_usd"], 3, 18), (E["aov"], 3, 18)],
                [(new_ids["kpi_refund_rate"], 3, 18), (E["gauge"], 9, 30)],
                [(E["rev_by_products"], 6, 50), (new_ids["rev_by_country_pie"], 6, 50)],
            ],
        },
        {
            "title": "Sales Trends",
            "rows": [
                [(E["trend_weekly"], 12, 50)],
                [(new_ids["sales_count_weekly"], 12, 50)],
                [(E["trend_monthly"], 12, 50)],
                [(E["rev_by_days"], 12, 50)],
                [(new_ids["heatmap_hour_day"], 6, 65), (new_ids["product_monthly_table"], 6, 65)],
            ],
        },
        {
            "title": "Product Analytics",
            "rows": [
                [(E["rev_by_products"], 6, 50), (new_ids["product_country_bar"], 6, 50)],
                [(new_ids["product_perf_table"], 12, 55)],
                [(new_ids["product_rev_trend"], 12, 50)],
                [(new_ids["product_vol_trend"], 12, 50)],
                [(new_ids["product_usertype_heatmap"], 12, 65)],
            ],
        },
        {
            "title": "Geography & Segments",
            "rows": [
                [(E["rev_by_user_type"], 4, 50), (new_ids["usertype_rev_trend"], 8, 50)],
                [(E["rev_by_cities"], 6, 50), (new_ids["top_cities_volume"], 6, 50)],
                [(new_ids["rev_by_country_trend"], 12, 50)],
                [(new_ids["city_product_table"], 12, 55)],
            ],
        },
        {
            "title": "Refunds & Health",
            "rows": [
                [(new_ids["kpi_refund_amount"], 4, 18), (new_ids["kpi_refund_count"], 4, 18)],
                [(E["top_refunded"], 6, 50), (new_ids["refund_rate_by_product"], 6, 50)],
                [(new_ids["refund_trend"], 12, 50)],
                [(new_ids["refund_timing"], 12, 50)],
            ],
        },
        {
            "title": "Raw Data",
            "rows": [
                [(E["data_table"], 12, 70)],
            ],
        },
    ]

    # Build position_json
    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": "Extra Sales"}},
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
            row_id = f"ROW-ES{row_counter}"
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


def main():
    print("=" * 60, file=sys.stderr)
    print("Extra Sales Dashboard Restructuring", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    # Step 1: Update gauge to USD
    print("\n[1/4] Updating gauge to 50K USD...", file=sys.stderr)
    update_gauge_to_usd(api)

    # Step 2: Create new charts
    print("\n[2/4] Creating new charts...", file=sys.stderr)
    new_ids = create_new_charts(api)
    print(f"\n  Created {len(new_ids)} new charts", file=sys.stderr)

    # Step 3: Build and apply layout
    print("\n[3/4] Building tabbed layout...", file=sys.stderr)
    position = build_layout(new_ids)

    # Read current dashboard to preserve json_metadata (filters etc.)
    data = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    current_metadata = json.loads(data["result"].get("json_metadata", "{}"))

    update_payload = {
        "position_json": json.dumps(position),
        "json_metadata": json.dumps(current_metadata),
    }
    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", update_payload)
    print("  Layout updated with 6 tabs", file=sys.stderr)

    # Step 4: Summary
    print("\n[4/4] Done!", file=sys.stderr)
    print(f"\n  Dashboard URL: {SUPERSET_URL}/superset/dashboard/{DASHBOARD_ID}/", file=sys.stderr)

    # Output summary as JSON
    summary = {
        "dashboard_id": DASHBOARD_ID,
        "url": f"{SUPERSET_URL}/superset/dashboard/{DASHBOARD_ID}/",
        "tabs": ["Overview & KPIs", "Sales Trends", "Product Analytics", "Geography & Segments", "Refunds & Health", "Raw Data"],
        "new_charts": {k: v for k, v in new_ids.items()},
        "existing_charts_relocated": list(EXISTING.keys()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
