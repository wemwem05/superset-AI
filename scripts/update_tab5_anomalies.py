#!/usr/bin/env python3
"""
Build out "Trends & Anomalies" section on TAB-5 (Operational Monitoring).

1. Replace chart #67 (broken CR vs MA) → mixed_timeseries: daily CR% bars + 30d MA line
2. New: Offer Volume + 30d MA (mixed_timeseries)
3. New: Day-of-Week CR% Heatmap (last 8 weeks)
4. New: Day-of-Week Offer Volume Heatmap (last 8 weeks)
5. New: Daily Deviation Table (last 14 days — date, offers, purchases, CR%, revenue)
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI, SUPERSET_URL, USERNAME, PASSWORD

DASHBOARD_ID = 5
DATASET_ID = 2
DS_UID = "2__table"

NO_DASHBOARD_DATE_FILTER = {
    "clause": "WHERE",
    "subject": "offer_date",
    "operator": "TEMPORAL_RANGE",
    "comparator": "No filter",
    "expressionType": "SIMPLE",
}

# ── 1. CR % with 30-day Moving Average (replace #67) ──────────────

CR_MA_CHART = {
    "name": "Comeback: Daily CR % + 30-day Moving Avg",
    "viz_type": "mixed_timeseries",
    "params": {
        "datasource": DS_UID,
        "viz_type": "mixed_timeseries",
        "x_axis": "offer_date",
        "time_grain_sqla": "P1D",
        # Series A: raw daily CR % as bars
        "metrics": [
            {
                "expressionType": "SQL",
                "sqlExpression": "COUNT(purchase_date)::NUMERIC / NULLIF(COUNT(offer_id), 0)",
                "hasCustomLabel": True,
                "label": "Daily CR %",
            }
        ],
        "groupby": [],
        "adhoc_filters": [NO_DASHBOARD_DATE_FILTER],
        "order_desc": True,
        "row_limit": 10000,
        "truncate_metric": True,
        "comparison_type": "values",
        # Series B: same metric but with 30-day rolling mean
        "metrics_b": [
            {
                "expressionType": "SQL",
                "sqlExpression": "COUNT(purchase_date)::NUMERIC / NULLIF(COUNT(offer_id), 0)",
                "hasCustomLabel": True,
                "label": "30-day MA",
            }
        ],
        "groupby_b": [],
        "adhoc_filters_b": [NO_DASHBOARD_DATE_FILTER],
        "order_desc_b": True,
        "row_limit_b": 10000,
        "truncate_metric_b": True,
        "comparison_type_b": "values",
        "rolling_type_b": "mean",
        "rolling_periods_b": 30,
        # Visual config
        "annotation_layers": [],
        "x_axis_title_margin": 15,
        "y_axis_title_margin": 15,
        "y_axis_title_position": "Left",
        "color_scheme": "supersetColors",
        # A: bars with low opacity
        "seriesType": "bar",
        "area": False,
        "show_value": False,
        "opacity": 0.3,
        "markerEnabled": False,
        "markerSize": 6,
        "yAxisIndex": 0,
        # B: smooth line on same Y axis
        "seriesTypeB": "line",
        "show_valueB": False,
        "opacityB": 0.8,
        "markerEnabledB": False,
        "markerSizeB": 6,
        "yAxisIndexB": 0,  # same axis as A
        # Legend & axes
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "%Y-%m-%d",
        "rich_tooltip": True,
        "tooltipTimeFormat": "%Y-%m-%d",
        "truncateXAxis": True,
        "y_axis_bounds": [None, None],
        "y_axis_format": ".2%",
        "y_axis_bounds_secondary": [None, None],
        "y_axis_format_secondary": ".2%",
    },
}

# ── 2. Offer Volume + 30-day Moving Average ───────────────────────

VOLUME_MA_CHART = {
    "name": "Comeback: Daily Offers + 30-day Moving Avg",
    "viz_type": "mixed_timeseries",
    "params": {
        "datasource": DS_UID,
        "viz_type": "mixed_timeseries",
        "x_axis": "offer_date",
        "time_grain_sqla": "P1D",
        # Series A: raw daily offer count as bars
        "metrics": [
            {
                "expressionType": "SQL",
                "sqlExpression": "COUNT(offer_id)",
                "hasCustomLabel": True,
                "label": "Daily Offers",
            }
        ],
        "groupby": [],
        "adhoc_filters": [NO_DASHBOARD_DATE_FILTER],
        "order_desc": True,
        "row_limit": 10000,
        "truncate_metric": True,
        "comparison_type": "values",
        # Series B: 30d rolling mean
        "metrics_b": [
            {
                "expressionType": "SQL",
                "sqlExpression": "COUNT(offer_id)",
                "hasCustomLabel": True,
                "label": "30-day MA",
            }
        ],
        "groupby_b": [],
        "adhoc_filters_b": [NO_DASHBOARD_DATE_FILTER],
        "order_desc_b": True,
        "row_limit_b": 10000,
        "truncate_metric_b": True,
        "comparison_type_b": "values",
        "rolling_type_b": "mean",
        "rolling_periods_b": 30,
        # Visual config
        "annotation_layers": [],
        "x_axis_title_margin": 15,
        "y_axis_title_margin": 15,
        "y_axis_title_position": "Left",
        "color_scheme": "supersetColors",
        "seriesType": "bar",
        "area": False,
        "show_value": False,
        "opacity": 0.3,
        "markerEnabled": False,
        "markerSize": 6,
        "yAxisIndex": 0,
        "seriesTypeB": "line",
        "show_valueB": False,
        "opacityB": 0.8,
        "markerEnabledB": False,
        "markerSizeB": 6,
        "yAxisIndexB": 0,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "%Y-%m-%d",
        "rich_tooltip": True,
        "tooltipTimeFormat": "%Y-%m-%d",
        "truncateXAxis": True,
        "y_axis_bounds": [None, None],
        "y_axis_format": "SMART_NUMBER",
        "y_axis_bounds_secondary": [None, None],
        "y_axis_format_secondary": "SMART_NUMBER",
    },
}

# ── 3. Day-of-Week CR % Heatmap ───────────────────────────────────

DOW_CR_HEATMAP = {
    "name": "Comeback: Day-of-Week CR % (Last 8 Weeks)",
    "viz_type": "heatmap",
    "params": {
        "datasource": DS_UID,
        "viz_type": "heatmap",
        "all_columns_x": {
            "expressionType": "SQL",
            "label": "Week",
            "sqlExpression": "TO_CHAR(offer_date, 'IYYY-\"W\"IW')",
        },
        "all_columns_y": {
            "expressionType": "SQL",
            "label": "Day of Week",
            "sqlExpression": "TO_CHAR(offer_date, 'Dy')",
        },
        "metric": {
            "expressionType": "SQL",
            "hasCustomLabel": True,
            "label": "CR %",
            "sqlExpression": "COUNT(purchase_date)::NUMERIC / NULLIF(COUNT(offer_id), 0)",
        },
        "adhoc_filters": [
            {
                "clause": "WHERE",
                "expressionType": "SQL",
                "sqlExpression": "offer_date >= CURRENT_DATE - INTERVAL '8 weeks'",
            },
            NO_DASHBOARD_DATE_FILTER,
        ],
        "row_limit": 10000,
        "linear_color_scheme": "superset_seq_1",
        "xscale_interval": 1,
        "yscale_interval": 1,
        "canvas_image_rendering": "pixelated",
        "normalize_across": "heatmap",
        "left_margin": 80,
        "bottom_margin": 80,
        "y_axis_bounds": [None, None],
        "y_axis_format": ".2%",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_legend": True,
        "show_perc": True,
        "show_values": True,
    },
}

# ── 4. Day-of-Week Offer Volume Heatmap ───────────────────────────

DOW_VOLUME_HEATMAP = {
    "name": "Comeback: Day-of-Week Offers (Last 8 Weeks)",
    "viz_type": "heatmap",
    "params": {
        "datasource": DS_UID,
        "viz_type": "heatmap",
        "all_columns_x": {
            "expressionType": "SQL",
            "label": "Week",
            "sqlExpression": "TO_CHAR(offer_date, 'IYYY-\"W\"IW')",
        },
        "all_columns_y": {
            "expressionType": "SQL",
            "label": "Day of Week",
            "sqlExpression": "TO_CHAR(offer_date, 'Dy')",
        },
        "metric": {
            "expressionType": "SQL",
            "hasCustomLabel": True,
            "label": "Offers",
            "sqlExpression": "COUNT(offer_id)",
        },
        "adhoc_filters": [
            {
                "clause": "WHERE",
                "expressionType": "SQL",
                "sqlExpression": "offer_date >= CURRENT_DATE - INTERVAL '8 weeks'",
            },
            NO_DASHBOARD_DATE_FILTER,
        ],
        "row_limit": 10000,
        "linear_color_scheme": "superset_seq_1",
        "xscale_interval": 1,
        "yscale_interval": 1,
        "canvas_image_rendering": "pixelated",
        "normalize_across": "heatmap",
        "left_margin": 80,
        "bottom_margin": 80,
        "y_axis_bounds": [None, None],
        "y_axis_format": "SMART_NUMBER",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_legend": True,
        "show_perc": True,
        "show_values": True,
    },
}

# ── 5. Daily Deviation Table (last 14 days) ───────────────────────

DEVIATION_TABLE = {
    "name": "Comeback: Daily Breakdown (Last 14 Days)",
    "viz_type": "table",
    "params": {
        "datasource": DS_UID,
        "viz_type": "table",
        "query_mode": "aggregate",
        "groupby": ["offer_date"],
        "time_grain_sqla": "P1D",
        "temporal_columns_lookup": {
            "offer_date": True,
            "send_to_amocrm_date": True,
            "purchase_date": True,
        },
        "metrics": [
            {
                "expressionType": "SQL",
                "sqlExpression": "COUNT(offer_id)",
                "hasCustomLabel": True,
                "label": "Offers",
            },
            {
                "expressionType": "SQL",
                "sqlExpression": "COUNT(purchase_date)",
                "hasCustomLabel": True,
                "label": "Purchases",
            },
            {
                "expressionType": "SQL",
                "sqlExpression": "COUNT(purchase_date)::NUMERIC / NULLIF(COUNT(offer_id), 0)",
                "hasCustomLabel": True,
                "label": "CR %",
            },
            {
                "expressionType": "SQL",
                "sqlExpression": "COALESCE(SUM(purchase_price_usd), 0)::int",
                "hasCustomLabel": True,
                "label": "Revenue USD",
            },
            {
                "expressionType": "SQL",
                "sqlExpression": "SUM(CASE WHEN send_to_amocrm THEN 1 ELSE 0 END)",
                "hasCustomLabel": True,
                "label": "Sent to CRM",
            },
            {
                "expressionType": "SQL",
                "sqlExpression": "SUM(CASE WHEN send_to_amocrm THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(offer_id), 0)",
                "hasCustomLabel": True,
                "label": "CRM Rate",
            },
        ],
        "all_columns": [],
        "percent_metrics": [],
        "adhoc_filters": [
            {
                "clause": "WHERE",
                "expressionType": "SQL",
                "sqlExpression": "offer_date >= CURRENT_DATE - INTERVAL '14 days'",
            },
            NO_DASHBOARD_DATE_FILTER,
        ],
        "timeseries_limit_metric": {
            "aggregate": "MAX",
            "column": {
                "column_name": "offer_date",
                "type": "DATE",
                "is_dttm": True,
            },
            "expressionType": "SIMPLE",
            "hasCustomLabel": False,
            "label": "MAX(offer_date)",
        },
        "order_by_cols": [],
        "row_limit": 50,
        "order_desc": True,
        "table_timestamp_format": "smart_date",
        "page_length": 0,
        "include_search": False,
        "allow_render_html": True,
        "column_config": {
            "CR %": {"d3NumberFormat": ".2%"},
            "CRM Rate": {"d3NumberFormat": ".1%"},
            "Revenue USD": {"d3NumberFormat": ","},
            "offer_date": {"d3TimeFormat": "%Y-%m-%d"},
        },
        "show_cell_bars": True,
        "color_pn": True,
        "conditional_formatting": [],
        "comparison_type": "values",
    },
}

ALL_NEW_CHARTS = [CR_MA_CHART, VOLUME_MA_CHART, DOW_CR_HEATMAP, DOW_VOLUME_HEATMAP, DEVIATION_TABLE]

# Chart #67 will be replaced by CR_MA_CHART
OLD_CHART_ID = 67


def create_chart(api, chart_def):
    payload = {
        "slice_name": chart_def["name"],
        "viz_type": chart_def["viz_type"],
        "datasource_id": DATASET_ID,
        "datasource_type": "table",
        "params": json.dumps(chart_def["params"]),
        "dashboards": [DASHBOARD_ID],
    }
    result = api.post("/api/v1/chart/", payload)
    chart_id = result["id"]
    print(f"  [+] Chart #{chart_id}: {chart_def['name']}", file=sys.stderr)
    return chart_id


def delete_old_chart(api, chart_id):
    """Remove old chart from dashboard and delete it."""
    try:
        api.delete(f"/api/v1/chart/{chart_id}")
        print(f"  [-] Deleted old chart #{chart_id}", file=sys.stderr)
    except Exception as e:
        print(f"  [!] Could not delete chart #{chart_id}: {e}", file=sys.stderr)


def update_layout(api, new_chart_ids):
    """
    Replace chart #67 with the new CR+MA chart, and add the remaining
    new charts into the Trends & Anomalies section of TAB-5.

    Layout plan (after the second HEADER in TAB-5):
      ROW: CR % + 30d MA (full width) — replaces old #67
      ROW: Offer Volume + 30d MA (full width)
      ROW: DoW CR% heatmap (6) | DoW Volume heatmap (6)
      ROW: Daily Deviation Table (full width)
    """
    data = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    position = json.loads(data["result"].get("position_json", "{}"))

    # Find TAB-5
    tab5_key = None
    for k, v in position.items():
        if isinstance(v, dict) and v.get("type") == "TAB" and v.get("meta", {}).get("text") == "Operational Monitoring":
            tab5_key = k
            break

    if not tab5_key:
        print("ERROR: Could not find Operational Monitoring tab!", file=sys.stderr)
        sys.exit(1)

    tab5_parents = ["ROOT_ID", "GRID_ID", "TABS-1", tab5_key]

    cr_ma_id, vol_ma_id, dow_cr_id, dow_vol_id, dev_table_id = new_chart_ids

    # ── Remove old chart #67 and its row from layout ──
    old_chart_key = f"CHART-{OLD_CHART_ID}"
    old_row_key = None
    for k, v in position.items():
        if isinstance(v, dict) and v.get("type") == "ROW":
            if old_chart_key in v.get("children", []):
                old_row_key = k
                break

    children = list(position[tab5_key]["children"])
    if old_row_key and old_row_key in children:
        children.remove(old_row_key)
        del position[old_row_key]
    if old_chart_key in position:
        del position[old_chart_key]

    # ── Build new rows ──

    # Row A: CR % + 30d MA (full width)
    row_a_key = "ROW-ANOM-CR-MA"
    chart_a_key = f"CHART-{cr_ma_id}"
    position[chart_a_key] = {
        "id": chart_a_key, "type": "CHART", "children": [],
        "parents": tab5_parents + [row_a_key],
        "meta": {"chartId": cr_ma_id, "height": 50, "sliceName": CR_MA_CHART["name"], "width": 12},
    }
    position[row_a_key] = {
        "id": row_a_key, "type": "ROW", "children": [chart_a_key],
        "parents": tab5_parents, "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }

    # Row B: Offer Volume + 30d MA (full width)
    row_b_key = "ROW-ANOM-VOL-MA"
    chart_b_key = f"CHART-{vol_ma_id}"
    position[chart_b_key] = {
        "id": chart_b_key, "type": "CHART", "children": [],
        "parents": tab5_parents + [row_b_key],
        "meta": {"chartId": vol_ma_id, "height": 50, "sliceName": VOLUME_MA_CHART["name"], "width": 12},
    }
    position[row_b_key] = {
        "id": row_b_key, "type": "ROW", "children": [chart_b_key],
        "parents": tab5_parents, "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }

    # Row C: Two heatmaps side by side
    row_c_key = "ROW-ANOM-DOW"
    chart_c1_key = f"CHART-{dow_cr_id}"
    chart_c2_key = f"CHART-{dow_vol_id}"
    position[chart_c1_key] = {
        "id": chart_c1_key, "type": "CHART", "children": [],
        "parents": tab5_parents + [row_c_key],
        "meta": {"chartId": dow_cr_id, "height": 60, "sliceName": DOW_CR_HEATMAP["name"], "width": 6},
    }
    position[chart_c2_key] = {
        "id": chart_c2_key, "type": "CHART", "children": [],
        "parents": tab5_parents + [row_c_key],
        "meta": {"chartId": dow_vol_id, "height": 60, "sliceName": DOW_VOLUME_HEATMAP["name"], "width": 6},
    }
    position[row_c_key] = {
        "id": row_c_key, "type": "ROW", "children": [chart_c1_key, chart_c2_key],
        "parents": tab5_parents, "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }

    # Row D: Deviation table (full width)
    row_d_key = "ROW-ANOM-DEVTBL"
    chart_d_key = f"CHART-{dev_table_id}"
    position[chart_d_key] = {
        "id": chart_d_key, "type": "CHART", "children": [],
        "parents": tab5_parents + [row_d_key],
        "meta": {"chartId": dev_table_id, "height": 55, "sliceName": DEVIATION_TABLE["name"], "width": 12},
    }
    position[row_d_key] = {
        "id": row_d_key, "type": "ROW", "children": [chart_d_key],
        "parents": tab5_parents, "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }

    # ── Find the second HEADER in TAB-5 (Trends section header) ──
    headers_found = 0
    insert_idx = len(children)
    for i, child_key in enumerate(children):
        child = position.get(child_key, {})
        if isinstance(child, dict) and child.get("type") == "HEADER":
            headers_found += 1
            if headers_found == 2:
                insert_idx = i + 1
                break

    # Insert new rows after the second header
    new_rows = [row_a_key, row_b_key, row_c_key, row_d_key]
    children = children[:insert_idx] + new_rows + children[insert_idx:]

    position[tab5_key]["children"] = children

    # Update dashboard
    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {"position_json": json.dumps(position)})
    print(f"  [+] Layout updated — TAB-5 now has {len(children)} children", file=sys.stderr)


def main():
    print("Connecting to Superset...", file=sys.stderr)
    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    print("Creating Trends & Anomalies charts...", file=sys.stderr)
    new_ids = []
    for chart_def in ALL_NEW_CHARTS:
        cid = create_chart(api, chart_def)
        new_ids.append(cid)

    print("Deleting old chart #67...", file=sys.stderr)
    delete_old_chart(api, OLD_CHART_ID)

    print("Updating TAB-5 layout...", file=sys.stderr)
    update_layout(api, new_ids)

    print("\nDone!", file=sys.stderr)
    output = {
        "deleted_chart": OLD_CHART_ID,
        "new_charts": [
            {"id": new_ids[i], "name": ALL_NEW_CHARTS[i]["name"]}
            for i in range(len(new_ids))
        ],
        "dashboard_url": f"{SUPERSET_URL}/superset/dashboard/{DASHBOARD_ID}/",
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
