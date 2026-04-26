#!/usr/bin/env python3
"""
Fix Call Center Analytics Overview KPI cards to match Comeback Leads style:
- header_font_size: 0.4, subheader_font_size: 0.15 (uniform)
- 4 cards per row, width 3 each (3 rows: 4+4+3)
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI

DASHBOARD_ID = 8

# All KPI chart IDs in the Overview tab
KPI_CHART_IDS = [119, 120, 121, 122, 123, 125, 126, 127, 128, 141, 142]

# Target font sizes (matching Comeback Leads Analytics)
TARGET_HEADER_FONT_SIZE = 0.4
TARGET_SUBHEADER_FONT_SIZE = 0.15


def update_chart_fonts(api):
    """Update header/subheader font sizes on all KPI cards."""
    for chart_id in KPI_CHART_IDS:
        params_update = {
            "header_font_size": TARGET_HEADER_FONT_SIZE,
            "subheader_font_size": TARGET_SUBHEADER_FONT_SIZE,
        }
        resp = api.get(f"/api/v1/chart/{chart_id}")
        current_params = json.loads(resp["result"]["params"])
        current_params.update(params_update)
        api.put(f"/api/v1/chart/{chart_id}", {"params": json.dumps(current_params)})
        print(f"  Updated chart {chart_id}: header={TARGET_HEADER_FONT_SIZE}, subheader={TARGET_SUBHEADER_FONT_SIZE}")


def rearrange_layout(api):
    """Rearrange KPI cards into 3 rows of 4+4+3, all width 3."""
    resp = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    position = json.loads(resp["result"]["position_json"])

    # Define new row layout: 3 rows
    rows = [
        {
            "key": "ROW-CC1",
            "charts": [
                (119, "Calls: Total Leads"),
                (120, "Calls: Leads Called"),
                (121, "Calls: Leads Answered"),
                (122, "Calls: Called in 15 min"),
            ],
        },
        {
            "key": "ROW-CC2",
            "charts": [
                (123, "Calls: Purchases"),
                (125, "Calls: CR to Call"),
                (126, "Calls: CR to Answered"),
                (127, "Calls: CR to Call in 15 min"),
            ],
        },
        {
            "key": "ROW-CC2B",
            "charts": [
                (128, "Calls: CR to Purchase"),
                (141, "Calls: Avg Time to First Call"),
                (142, "Calls: Avg Calls per Lead"),
            ],
        },
    ]

    # Find TAB-1 to get its parents
    tab1_parents = position["TAB-1"]["parents"]

    # Remove old ROW-CC1 and ROW-CC2 and their chart entries from position
    old_row_keys = ["ROW-CC1", "ROW-CC2"]
    old_chart_keys = []
    for key in old_row_keys:
        if key in position:
            for child_key in position[key].get("children", []):
                old_chart_keys.append(child_key)
            del position[key]
    for ck in old_chart_keys:
        if ck in position:
            del position[ck]

    # Remove old rows from TAB-1 children
    tab1_children = position["TAB-1"]["children"]
    tab1_children = [c for c in tab1_children if c not in old_row_keys]

    # Find insertion point (beginning of TAB-1 children)
    # Build new rows and charts
    new_row_keys = []
    for row_def in rows:
        row_key = row_def["key"]
        chart_children = []

        for chart_id, slice_name in row_def["charts"]:
            chart_key = f"CHART-{chart_id}"
            chart_children.append(chart_key)
            position[chart_key] = {
                "id": chart_key,
                "type": "CHART",
                "children": [],
                "parents": tab1_parents + ["TAB-1", row_key],
                "meta": {
                    "chartId": chart_id,
                    "width": 3,
                    "height": 18,
                    "sliceName": slice_name,
                    "uuid": f"kpi-{chart_id}",
                },
            }

        position[row_key] = {
            "id": row_key,
            "type": "ROW",
            "children": chart_children,
            "parents": tab1_parents + ["TAB-1"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        new_row_keys.append(row_key)

    # Insert new rows at the beginning of TAB-1
    position["TAB-1"]["children"] = new_row_keys + tab1_children

    # Save
    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {"position_json": json.dumps(position)})
    print("  Layout updated: 3 rows (4+4+3), all width 3")


def main():
    from create_dashboard import SUPERSET_URL, USERNAME, PASSWORD
    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    print("Step 1: Updating KPI card font sizes...")
    update_chart_fonts(api)

    print("Step 2: Rearranging layout...")
    rearrange_layout(api)

    print("\nDone! Refresh the Call Center Analytics dashboard to see changes.")


if __name__ == "__main__":
    main()
