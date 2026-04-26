#!/usr/bin/env python3
"""
Add "Yesterday" section charts to TAB-5 (Operational Monitoring)
on the Comeback Leads Analytics dashboard.

Creates:
  - Row 1: 4 KPI cards (Offers, Purchases, CR%, Revenue USD)
  - Row 2: 4 KPI cards (Sent to CRM, Not Sent, CRM Rate%, Avg Check)
  - Row 3: Yesterday by Country table
Then updates the dashboard layout to place them at the top of TAB-5,
before the existing charts.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI, SUPERSET_URL, USERNAME, PASSWORD

DASHBOARD_ID = 5
DATASET_UID = "2__table"

YESTERDAY_FILTER = [
    {
        "clause": "WHERE",
        "expressionType": "SQL",
        "sqlExpression": "offer_date = CURRENT_DATE - 1",
    },
    {
        "clause": "WHERE",
        "subject": "offer_date",
        "operator": "TEMPORAL_RANGE",
        "comparator": "No filter",
        "expressionType": "SIMPLE",
    },
]

BIG_NUM_BASE = {
    "datasource": DATASET_UID,
    "viz_type": "big_number_total",
    "header_font_size": 0.4,
    "subheader_font_size": 0.15,
    "y_axis_format": "SMART_NUMBER",
    "time_format": "smart_date",
    "conditional_formatting": [],
    "adhoc_filters": YESTERDAY_FILTER,
}


def make_big_number(name, sql_expr, label, extra=None):
    params = {
        **BIG_NUM_BASE,
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": sql_expr,
            "hasCustomLabel": True,
            "label": label,
        },
    }
    if extra:
        params.update(extra)
    return {"name": name, "viz_type": "big_number_total", "params": params}


# ── Chart definitions ──────────────────────────────────────────────

ROW1_CHARTS = [
    make_big_number(
        "Yesterday: Total Offers",
        "COUNT(offer_id)",
        "Offers",
    ),
    make_big_number(
        "Yesterday: Purchases",
        "COUNT(purchase_date)",
        "Purchases",
    ),
    make_big_number(
        "Yesterday: CR %",
        "COUNT(purchase_date)::NUMERIC / NULLIF(COUNT(offer_id), 0)",
        "CR %",
        {"y_axis_format": ".2%"},
    ),
    make_big_number(
        "Yesterday: Revenue (USD)",
        "COALESCE(SUM(purchase_price_usd), 0)::int",
        "Revenue USD",
        {"currency_format": {"symbol": "USD"}},
    ),
]

ROW2_CHARTS = [
    make_big_number(
        "Yesterday: Sent to CRM",
        "SUM(CASE WHEN send_to_amocrm THEN 1 ELSE 0 END)",
        "Sent to CRM",
    ),
    make_big_number(
        "Yesterday: Not Sent to CRM",
        "SUM(CASE WHEN NOT send_to_amocrm THEN 1 ELSE 0 END)",
        "Not in CRM",
    ),
    make_big_number(
        "Yesterday: CRM Send Rate",
        "SUM(CASE WHEN send_to_amocrm THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(offer_id), 0)",
        "CRM Rate",
        {"y_axis_format": ".1%"},
    ),
    make_big_number(
        "Yesterday: Avg Check (USD)",
        "ROUND(AVG(purchase_price_usd) FILTER (WHERE purchase_date IS NOT NULL)::NUMERIC, 0)",
        "Avg Check",
        {"currency_format": {"symbol": "USD"}},
    ),
]

COUNTRY_TABLE = {
    "name": "Yesterday: Performance by Country",
    "viz_type": "table",
    "params": {
        "datasource": DATASET_UID,
        "viz_type": "table",
        "query_mode": "aggregate",
        "groupby": ["country"],
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
                "sqlExpression": "ROUND(AVG(purchase_price_usd) FILTER (WHERE purchase_date IS NOT NULL)::NUMERIC, 0)",
                "hasCustomLabel": True,
                "label": "Avg Check USD",
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
        "adhoc_filters": YESTERDAY_FILTER,
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
            "Avg Check USD": {"d3NumberFormat": ","},
        },
        "show_cell_bars": True,
        "color_pn": True,
        "conditional_formatting": [],
        "comparison_type": "values",
    },
}

ALL_CHARTS = ROW1_CHARTS + ROW2_CHARTS + [COUNTRY_TABLE]


def create_charts(api):
    """Create all charts and return list of (chart_id, name, group)."""
    created = []
    for i, chart_def in enumerate(ALL_CHARTS):
        params = chart_def["params"]
        payload = {
            "slice_name": chart_def["name"],
            "viz_type": chart_def["viz_type"],
            "datasource_id": 2,
            "datasource_type": "table",
            "params": json.dumps(params),
            "dashboards": [DASHBOARD_ID],
        }
        result = api.post("/api/v1/chart/", payload)
        chart_id = result["id"]
        if i < 4:
            group = "row1"
        elif i < 8:
            group = "row2"
        else:
            group = "country_table"
        created.append({"id": chart_id, "name": chart_def["name"], "group": group})
        print(f"  [+] Chart #{chart_id}: {chart_def['name']}", file=sys.stderr)
    return created


def update_layout(api, created_charts):
    """Insert new charts into TAB-5 layout, right after the first HEADER."""
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

    tab5 = position[tab5_key]
    tab5_parents = ["ROOT_ID", "GRID_ID", "TABS-1", tab5_key]

    # Build new rows
    row1_ids = [c["id"] for c in created_charts if c["group"] == "row1"]
    row2_ids = [c["id"] for c in created_charts if c["group"] == "row2"]
    country_id = [c["id"] for c in created_charts if c["group"] == "country_table"][0]

    # Generate unique row keys
    new_row1_key = "ROW-YEST-KPI1"
    new_row2_key = "ROW-YEST-KPI2"
    new_row3_key = "ROW-YEST-COUNTRY"

    # Row 1: 4 KPI cards
    row1_children = []
    for cid in row1_ids:
        chart_key = f"CHART-{cid}"
        row1_children.append(chart_key)
        position[chart_key] = {
            "id": chart_key,
            "type": "CHART",
            "children": [],
            "parents": tab5_parents + [new_row1_key],
            "meta": {
                "chartId": cid,
                "height": 18,
                "sliceName": next(c["name"] for c in created_charts if c["id"] == cid),
                "width": 3,
            },
        }
    position[new_row1_key] = {
        "id": new_row1_key,
        "type": "ROW",
        "children": row1_children,
        "parents": tab5_parents,
        "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }

    # Row 2: 4 KPI cards
    row2_children = []
    for cid in row2_ids:
        chart_key = f"CHART-{cid}"
        row2_children.append(chart_key)
        position[chart_key] = {
            "id": chart_key,
            "type": "CHART",
            "children": [],
            "parents": tab5_parents + [new_row2_key],
            "meta": {
                "chartId": cid,
                "height": 18,
                "sliceName": next(c["name"] for c in created_charts if c["id"] == cid),
                "width": 3,
            },
        }
    position[new_row2_key] = {
        "id": new_row2_key,
        "type": "ROW",
        "children": row2_children,
        "parents": tab5_parents,
        "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }

    # Row 3: Country table (full width, next to existing city table)
    country_chart_key = f"CHART-{country_id}"
    position[country_chart_key] = {
        "id": country_chart_key,
        "type": "CHART",
        "children": [],
        "parents": tab5_parents + [new_row3_key],
        "meta": {
            "chartId": country_id,
            "height": 30,
            "sliceName": "Yesterday: Performance by Country",
            "width": 6,
        },
    }

    # Find the existing city table row to put country table alongside it
    # The city table (chart 65) is in ROW-ygb0ZvJ3dY06pM_0Ddhhn
    city_row_key = "ROW-ygb0ZvJ3dY06pM_0Ddhhn"
    if city_row_key in position:
        # Add country table to the same row as city table
        position[city_row_key]["children"].insert(0, country_chart_key)
        position[country_chart_key]["parents"] = tab5_parents + [city_row_key]
        # No need for new_row3_key
        use_separate_country_row = False
    else:
        # Fallback: separate row
        position[new_row3_key] = {
            "id": new_row3_key,
            "type": "ROW",
            "children": [country_chart_key],
            "parents": tab5_parents,
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        use_separate_country_row = True

    # Insert new rows into TAB-5 children, right after the first HEADER
    children = tab5["children"]
    # Find the first HEADER (the "Yesterday" section header)
    insert_idx = 0
    for i, child_key in enumerate(children):
        child = position.get(child_key, {})
        if isinstance(child, dict) and child.get("type") == "HEADER":
            insert_idx = i + 1
            break

    # Insert KPI rows after the header
    new_children = children[:insert_idx] + [new_row1_key, new_row2_key]
    if use_separate_country_row:
        new_children.append(new_row3_key)
    new_children += children[insert_idx:]

    position[tab5_key]["children"] = new_children

    # Update dashboard
    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {"position_json": json.dumps(position)})
    print(f"  [+] Dashboard layout updated — TAB-5 now has {len(new_children)} children", file=sys.stderr)


def main():
    print("Connecting to Superset...", file=sys.stderr)
    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    print("Creating Yesterday section charts...", file=sys.stderr)
    created = create_charts(api)

    print("Updating TAB-5 layout...", file=sys.stderr)
    update_layout(api, created)

    print("\nDone! New charts:", file=sys.stderr)
    output = {
        "new_charts": [{"id": c["id"], "name": c["name"]} for c in created],
        "dashboard_url": f"{SUPERSET_URL}/superset/dashboard/{DASHBOARD_ID}/",
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
