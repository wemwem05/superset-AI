#!/usr/bin/env python3
"""
Rebuild Call Center Analytics → Breakdowns tab:
- Fix broken call_in_15_minutes references in existing tables
- Add missing dimensions: lead_source, user_city, device_vendor
- Add efficiency metrics: avg_calls_per_lead, median_time_to_first_call
- Remove revenue metrics
- Update heatmap to CR 15min, add cross-dimension heatmaps
- Rearrange layout
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI, SUPERSET_URL, USERNAME, PASSWORD

DASHBOARD_ID = 8
DATASOURCE = "5__table"

TEMPORAL_FILTER = {
    "clause": "WHERE",
    "subject": "lead_time",
    "operator": "TEMPORAL_RANGE",
    "comparator": "No filter",
    "expressionType": "SIMPLE",
}

# Standard metrics for all breakdown tables (no revenue)
TABLE_METRICS = [
    {"expressionType": "SQL", "sqlExpression": "COUNT(lead_id)", "hasCustomLabel": True, "label": "Leads"},
    {"expressionType": "SQL", "sqlExpression": "SUM(CASE WHEN calls_count > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(lead_id), 0)", "hasCustomLabel": True, "label": "CR Call"},
    {"expressionType": "SQL", "sqlExpression": "SUM(CASE WHEN first_call_time - lead_time < '15 minutes'::interval THEN 1 ELSE 0 END)::float / NULLIF(COUNT(lead_id), 0)", "hasCustomLabel": True, "label": "CR 15min"},
    {"expressionType": "SQL", "sqlExpression": "SUM(CASE WHEN answered_calls_count > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(lead_id), 0)", "hasCustomLabel": True, "label": "CR Answered"},
    {"expressionType": "SQL", "sqlExpression": "SUM(CASE WHEN purchase THEN 1 ELSE 0 END)::float / NULLIF(COUNT(lead_id), 0)", "hasCustomLabel": True, "label": "CR Purchase"},
    {"expressionType": "SQL", "sqlExpression": "ROUND(AVG(calls_count)::numeric, 2)", "hasCustomLabel": True, "label": "Avg Calls"},
    {"expressionType": "SQL", "sqlExpression": "(percentile_disc(0.5) within group (order by extract(epoch from first_call_time - lead_time)))::numeric / 60.0", "hasCustomLabel": True, "label": "Med. Time (min)"},
]

TABLE_COLUMN_CONFIG = {
    "CR Call": {"d3NumberFormat": ".1%"},
    "CR 15min": {"d3NumberFormat": ".1%"},
    "CR Answered": {"d3NumberFormat": ".1%"},
    "CR Purchase": {"d3NumberFormat": ".1%"},
    "Avg Calls": {"d3NumberFormat": ",.2f"},
    "Med. Time (min)": {"d3NumberFormat": ",.1f"},
}


def make_table_params(groupby, row_limit=50):
    return {
        "datasource": DATASOURCE,
        "viz_type": "table",
        "query_mode": "aggregate",
        "groupby": groupby,
        "metrics": TABLE_METRICS,
        "order_desc": True,
        "row_limit": row_limit,
        "show_totals": True,
        "show_cell_bars": True,
        "color_pn": True,
        "page_length": 20,
        "column_config": TABLE_COLUMN_CONFIG,
        "adhoc_filters": [TEMPORAL_FILTER],
    }


def update_existing_tables(api):
    """Fix charts 131 (device_type), 132 (country), 133 (age_group)."""
    updates = [
        (131, "Calls: by Device Type", ["device_type"]),
        (132, "Calls: by Country", ["country"]),
        (133, "Calls: by Age Group", ["age_group"]),
    ]
    for chart_id, name, groupby in updates:
        params = make_table_params(groupby)
        resp = api.get(f"/api/v1/chart/{chart_id}")
        current = json.loads(resp["result"]["params"])
        current.update(params)
        api.put(f"/api/v1/chart/{chart_id}", {"params": json.dumps(current)})
        print(f"  Fixed chart {chart_id}: {name}")


def create_chart(api, name, params):
    """Create a new chart and return its ID."""
    payload = {
        "slice_name": name,
        "viz_type": params["viz_type"],
        "datasource_id": 5,
        "datasource_type": "table",
        "params": json.dumps(params),
        "dashboards": [DASHBOARD_ID],
    }
    resp = api.post("/api/v1/chart/", payload)
    chart_id = resp["id"]
    print(f"  Created chart {chart_id}: {name}")
    return chart_id


def create_new_tables(api):
    """Create tables for lead_source, user_city, device_vendor."""
    new_charts = {}

    # By Lead Source (full width, top)
    params = make_table_params(["lead_source"])
    new_charts["lead_source"] = create_chart(api, "Calls: by Lead Source", params)

    # By City (Top 20)
    params = make_table_params(["user_city"], row_limit=20)
    new_charts["user_city"] = create_chart(api, "Calls: by City (Top 20)", params)

    # By Device Vendor (Top 20)
    params = make_table_params(["device_vendor"], row_limit=20)
    new_charts["device_vendor"] = create_chart(api, "Calls: by Device Vendor (Top 20)", params)

    return new_charts


def update_heatmap_135(api):
    """Change heatmap 135 from CR Answered → CR to Call in 15 min."""
    resp = api.get(f"/api/v1/chart/135")
    current = json.loads(resp["result"]["params"])
    current["metric"] = {
        "expressionType": "SQL",
        "sqlExpression": "SUM(CASE WHEN first_call_time - lead_time < '15 minutes'::interval THEN 1 ELSE 0 END)::float / NULLIF(COUNT(lead_id), 0)",
        "hasCustomLabel": True,
        "label": "CR 15min",
    }
    current["value_format"] = ".1%"
    api.put(f"/api/v1/chart/135", {
        "slice_name": "Calls: CR 15min by Hour & Day of Week",
        "params": json.dumps(current),
    })
    print("  Updated chart 135: CR Answered → CR 15min heatmap")


def create_cross_heatmaps(api):
    """Create two cross-dimension heatmaps."""
    new_charts = {}

    # Lead Source × Country: CR to Call
    params = {
        "datasource": DATASOURCE,
        "viz_type": "heatmap",
        "all_columns_x": {"expressionType": "SQL", "label": "Country", "sqlExpression": "country"},
        "all_columns_y": {"expressionType": "SQL", "label": "Lead Source", "sqlExpression": "lead_source"},
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "SUM(CASE WHEN calls_count > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(lead_id), 0)",
            "hasCustomLabel": True,
            "label": "CR Call",
        },
        "linear_color_scheme": "superset_seq_1",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_values": True,
        "normalize_across": "heatmap",
        "value_format": ".1%",
        "adhoc_filters": [TEMPORAL_FILTER],
    }
    new_charts["source_country"] = create_chart(api, "Calls: CR to Call — Lead Source × Country", params)

    # Device Type × Age Group: CR to Purchase
    params2 = {
        "datasource": DATASOURCE,
        "viz_type": "heatmap",
        "all_columns_x": {"expressionType": "SQL", "label": "Age Group", "sqlExpression": "age_group"},
        "all_columns_y": {"expressionType": "SQL", "label": "Device Type", "sqlExpression": "device_type"},
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "SUM(CASE WHEN purchase THEN 1 ELSE 0 END)::float / NULLIF(COUNT(lead_id), 0)",
            "hasCustomLabel": True,
            "label": "CR Purchase",
        },
        "linear_color_scheme": "superset_seq_1",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_values": True,
        "normalize_across": "heatmap",
        "value_format": ".1%",
        "adhoc_filters": [TEMPORAL_FILTER],
    }
    new_charts["device_age"] = create_chart(api, "Calls: CR to Purchase — Device × Age Group", params2)

    return new_charts


def rebuild_layout(api, new_table_ids, new_heatmap_ids):
    """Rearrange TAB-2 layout."""
    resp = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    position = json.loads(resp["result"]["position_json"])

    tab2_parents = position["TAB-2"]["parents"]
    base_parents = tab2_parents + ["TAB-2"]

    # Remove all existing TAB-2 children from position
    old_children = list(position["TAB-2"]["children"])
    to_remove = set()
    for child_key in old_children:
        to_remove.add(child_key)
        if child_key in position:
            for grandchild in position[child_key].get("children", []):
                to_remove.add(grandchild)
    for key in to_remove:
        if key in position:
            del position[key]

    # Build new layout
    rows = []

    def add_row(row_key, chart_defs):
        """chart_defs: list of (chart_id, name, width, height)"""
        children = []
        for cid, cname, w, h in chart_defs:
            ck = f"CHART-{cid}"
            children.append(ck)
            position[ck] = {
                "id": ck,
                "type": "CHART",
                "children": [],
                "parents": base_parents + [row_key],
                "meta": {"chartId": cid, "width": w, "height": h, "sliceName": cname},
            }
        position[row_key] = {
            "id": row_key,
            "type": "ROW",
            "children": children,
            "parents": base_parents,
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        rows.append(row_key)

    # Row 1: by Lead Source (full width)
    add_row("ROW-BD1", [
        (new_table_ids["lead_source"], "Calls: by Lead Source", 12, 50),
    ])

    # Row 2: by Country + by Device Type
    add_row("ROW-BD2", [
        (132, "Calls: by Country", 6, 50),
        (131, "Calls: by Device Type", 6, 50),
    ])

    # Row 3: by City (Top 20) + by Age Group
    add_row("ROW-BD3", [
        (new_table_ids["user_city"], "Calls: by City (Top 20)", 6, 50),
        (133, "Calls: by Age Group", 6, 50),
    ])

    # Row 4: by Device Vendor (full width)
    add_row("ROW-BD4", [
        (new_table_ids["device_vendor"], "Calls: by Device Vendor (Top 20)", 12, 50),
    ])

    # Row 5: Heatmaps — Leads by Hour/Day + CR 15min by Hour/Day
    add_row("ROW-BD5", [
        (134, "Calls: Leads by Hour & Day of Week", 6, 70),
        (135, "Calls: CR 15min by Hour & Day of Week", 6, 70),
    ])

    # Row 6: Cross-dimension heatmaps
    add_row("ROW-BD6", [
        (new_heatmap_ids["source_country"], "Calls: CR to Call — Lead Source × Country", 6, 70),
        (new_heatmap_ids["device_age"], "Calls: CR to Purchase — Device × Age Group", 6, 70),
    ])

    position["TAB-2"]["children"] = rows

    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {"position_json": json.dumps(position)})
    print("  Layout rebuilt: 6 rows")


def main():
    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    print("Step 1: Fix existing tables (remove revenue, fix CR 15min)...")
    update_existing_tables(api)

    print("Step 2: Create new dimension tables...")
    new_table_ids = create_new_tables(api)

    print("Step 3: Update heatmap 135 → CR 15min...")
    update_heatmap_135(api)

    print("Step 4: Create cross-dimension heatmaps...")
    new_heatmap_ids = create_cross_heatmaps(api)

    print("Step 5: Rebuild layout...")
    rebuild_layout(api, new_table_ids, new_heatmap_ids)

    print("\nDone! Refresh the Call Center Analytics → Breakdowns tab.")


if __name__ == "__main__":
    main()
