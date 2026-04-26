#!/usr/bin/env python3
"""
Replace the ECharts gauge with a beautiful SVG handlebars gauge on the Extra Sales dashboard.

Creates a handlebars chart with an SVG semicircle gauge that:
- Shows current revenue vs $50K target
- Uses color gradient (green → yellow → red zones)
- Has clean typography and minimal margins
- Responds to dashboard date filters
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI, SUPERSET_URL, USERNAME, PASSWORD

DASHBOARD_ID = 2
DATASET_ID = 1
DATASET_UID = "1__table"
OLD_GAUGE_ID = 1

TEMPORAL_PASSTHROUGH = {
    "clause": "WHERE",
    "subject": "purchase_date",
    "operator": "TEMPORAL_RANGE",
    "comparator": "No filter",
    "expressionType": "SIMPLE",
}

# The handlebars template — pure CSS + SVG, no JavaScript needed
HANDLEBARS_TEMPLATE = r"""
<style>
  .rev-gauge-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    width: 100%;
    font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    padding: 8px 0 0 0;
    box-sizing: border-box;
  }
  .rev-gauge-svg-wrap {
    position: relative;
    width: 340px;
    height: 190px;
    overflow: hidden;
  }
  .rev-gauge-center {
    position: absolute;
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
    text-align: center;
  }
  .rev-gauge-value {
    font-size: 38px;
    font-weight: 800;
    color: #1a1a2e;
    line-height: 1;
    letter-spacing: -1px;
  }
  .rev-gauge-target {
    font-size: 13px;
    font-weight: 500;
    color: #9ca3af;
    margin-top: 4px;
  }
  .rev-gauge-title {
    font-size: 15px;
    font-weight: 600;
    color: #6b7280;
    margin-top: 8px;
    letter-spacing: 0.5px;
  }
  .rev-gauge-pct {
    font-size: 13px;
    font-weight: 600;
    color: #6366f1;
    margin-top: 2px;
  }
</style>

{{#each data}}
<div class="rev-gauge-wrap">
  <div class="rev-gauge-svg-wrap">
    <svg width="340" height="190" viewBox="0 0 340 190" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#10b981" />
          <stop offset="50%" stop-color="#f59e0b" />
          <stop offset="100%" stop-color="#6366f1" />
        </linearGradient>
      </defs>
      <!-- Background track -->
      <circle cx="170" cy="170" r="140"
        fill="none"
        stroke="#f3f4f6"
        stroke-width="22"
        stroke-dasharray="439.82 439.82"
        stroke-linecap="round"
        transform="rotate(180 170 170)" />
      <!-- Filled arc — dashoffset drives the fill percentage -->
      <circle cx="170" cy="170" r="140"
        fill="none"
        stroke="url(#gaugeGrad)"
        stroke-width="22"
        stroke-dasharray="439.82 439.82"
        stroke-dashoffset="{{this.arc_offset}}"
        stroke-linecap="round"
        transform="rotate(180 170 170)" />
      <!-- Min label -->
      <text x="22" y="185" font-size="12" font-weight="500" fill="#9ca3af" text-anchor="start" font-family="Inter, sans-serif">$0</text>
      <!-- Max label -->
      <text x="318" y="185" font-size="12" font-weight="500" fill="#9ca3af" text-anchor="end" font-family="Inter, sans-serif">$50K</text>
    </svg>
    <div class="rev-gauge-center">
      <div class="rev-gauge-value">${{this.revenue_display}}</div>
      <div class="rev-gauge-target">of $50,000 target</div>
    </div>
  </div>
  <div class="rev-gauge-pct">{{this.pct_display}}% achieved</div>
</div>
{{/each}}
"""


def create_handlebars_gauge(api):
    """Create a handlebars chart that renders an SVG gauge."""

    # The SQL metrics compute:
    # 1. revenue_display: formatted revenue string (e.g., "12,345")
    # 2. pct_display: percentage of $50K target (e.g., "24.7")
    # 3. arc_offset: the SVG stroke-dashoffset value for the arc fill
    #    semicircle circumference = pi * 140 = 439.82
    #    offset = 439.82 - (439.82 * min(pct/100, 1))
    #    = 439.82 * (1 - min(revenue/50000, 1))

    params = {
        "datasource": DATASET_UID,
        "viz_type": "handlebars",
        "query_mode": "aggregate",
        "groupby": [],
        "metrics": [
            {
                "expressionType": "SQL",
                "sqlExpression": "TO_CHAR(SUM(price_usd)::int, 'FM999,999')",
                "hasCustomLabel": True,
                "label": "revenue_display",
            },
            {
                "expressionType": "SQL",
                "sqlExpression": "ROUND(LEAST(SUM(price_usd) / 50000.0 * 100, 100), 1)::text",
                "hasCustomLabel": True,
                "label": "pct_display",
            },
            {
                "expressionType": "SQL",
                "sqlExpression": "ROUND(439.82 * (1.0 - LEAST(SUM(price_usd) / 50000.0, 1.0)), 2)::text",
                "hasCustomLabel": True,
                "label": "arc_offset",
            },
        ],
        "adhoc_filters": [TEMPORAL_PASSTHROUGH],
        "row_limit": 1,
        "handlebarsTemplate": HANDLEBARS_TEMPLATE,
    }

    payload = {
        "slice_name": "Extra Revenue Target (50K USD)",
        "viz_type": "handlebars",
        "datasource_id": DATASET_ID,
        "datasource_type": "table",
        "params": json.dumps(params),
        "dashboards": [DASHBOARD_ID],
    }

    result = api.post("/api/v1/chart/", payload)
    chart_id = result["id"]
    print(f"  [+] Created handlebars gauge: chart #{chart_id}", file=sys.stderr)
    return chart_id


def swap_in_layout(api, new_chart_id):
    """Replace the old gauge (chart #1) with the new handlebars gauge in the layout."""
    data = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    position = json.loads(data["result"]["position_json"])

    old_key = f"CHART-{OLD_GAUGE_ID}"
    new_key = f"CHART-{new_chart_id}"

    # Find the old gauge's parent row
    if old_key not in position:
        print(f"  [!] Old gauge CHART-{OLD_GAUGE_ID} not found in layout", file=sys.stderr)
        return

    old_node = position[old_key]
    parent_row_id = old_node["parents"][-1]

    # Create the new chart node
    position[new_key] = {
        "id": new_key,
        "type": "CHART",
        "children": [],
        "parents": old_node["parents"],
        "meta": {
            "chartId": new_chart_id,
            "width": 12,
            "height": 38,
            "sliceName": "Extra Revenue Target (50K USD)",
        },
    }

    # Replace in parent's children
    parent_row = position[parent_row_id]
    parent_row["children"] = [new_key if c == old_key else c for c in parent_row["children"]]

    # Remove old node
    del position[old_key]

    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {
        "position_json": json.dumps(position),
    })
    print(f"  [~] Layout: swapped CHART-{OLD_GAUGE_ID} → CHART-{new_chart_id}", file=sys.stderr)


def remove_old_gauge_css(api):
    """Remove the old gauge CSS from the dashboard."""
    data = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    current_css = data["result"].get("css", "") or ""

    # Remove old gauge CSS
    if "Gauge chart #1" in current_css:
        api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {"css": ""})
        print("  [~] Removed old gauge CSS", file=sys.stderr)


def main():
    print("=" * 60, file=sys.stderr)
    print("Creating SVG Handlebars Gauge", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    print("\n[1/3] Creating handlebars gauge chart...", file=sys.stderr)
    new_id = create_handlebars_gauge(api)

    print("\n[2/3] Swapping gauge in dashboard layout...", file=sys.stderr)
    swap_in_layout(api, new_id)

    print("\n[3/3] Cleaning up old CSS...", file=sys.stderr)
    remove_old_gauge_css(api)

    print(f"\nDone! New gauge is chart #{new_id}", file=sys.stderr)
    print(f"Dashboard: {SUPERSET_URL}/superset/dashboard/{DASHBOARD_ID}/", file=sys.stderr)


if __name__ == "__main__":
    main()
