#!/usr/bin/env python3
"""
Fix styling on the "Overview & KPIs" tab of the Extra Sales dashboard (ID: 2).

1. Restyle the gauge chart: minimize offsets so the arc fills the card
2. Inject dashboard CSS to remove container padding around the gauge
3. Reduce gauge card height so there's less empty space
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from create_dashboard import SupersetAPI, SUPERSET_URL, USERNAME, PASSWORD

DASHBOARD_ID = 2
GAUGE_CHART_ID = 1


def fix_gauge_params(api):
    """Minimize fixed-pixel offsets in the gauge so the arc fills its container.

    The ECharts gauge radius = min(w,h)/2 - axisLabelDistance - axisTickDistance.
    By disabling ticks, split lines, and using a small font_size, we minimize
    those subtractions and let the arc be as large as possible.
    """
    data = api.get(f"/api/v1/chart/{GAUGE_CHART_ID}")
    params = json.loads(data["result"]["params"])

    params.update({
        # Semicircle (180°) — wider arc, less vertical waste
        "start_angle": 180,
        "end_angle": 0,
        # Small font_size reduces axisLabelDistance (1.5 * fontSize * 0.35 * ...)
        # but we still want the value readable, so 15 is a good balance
        "font_size": 15,
        # Clean number format
        "number_format": ",.0f",
        "value_formatter": "{value}",
        # Disable everything that subtracts from radius
        "show_axis_tick": False,
        "show_split_line": False,
        "show_progress": True,
        "overlap": True,
        "round_cap": True,
        # Pointer and animation
        "show_pointer": True,
        "animation": True,
        # Minimal splits
        "split_number": 5,
        # Color intervals
        "intervals": [20000, 35000, 50000],
        "interval_color_indices": "1,5,9",
        "color_scheme": "blueToGreen",
    })

    api.put(f"/api/v1/chart/{GAUGE_CHART_ID}", {"params": json.dumps(params)})
    print(f"  [~] Chart #{GAUGE_CHART_ID}: params optimized for max arc size", file=sys.stderr)


def inject_gauge_css(api):
    """Inject CSS into the dashboard to strip padding/margins around the gauge card."""
    css = """
/* === Gauge chart #1: strip all container padding so canvas fills the card === */
.dashboard-chart-id-1 {
  overflow: hidden !important;
}
.dashboard-chart-id-1 .chart-container {
  padding: 0 !important;
  margin: 0 !important;
}
.dashboard-chart-id-1 .slice_container {
  padding: 0 !important;
  margin: 0 !important;
}
.dashboard-chart-id-1 .header-title {
  padding: 2px 8px !important;
  min-height: 0 !important;
  font-size: 13px !important;
  line-height: 1.2 !important;
}
/* Push canvas to fill available space */
.dashboard-chart-id-1 div[data-test="chart-container"] {
  padding: 0 !important;
  margin: 0 !important;
}
""".strip()

    # Read current dashboard to preserve existing css
    data = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    current_css = data["result"].get("css", "") or ""

    # Remove any previous gauge CSS we injected (idempotent)
    marker_start = "/* === Gauge chart #1:"
    if marker_start in current_css:
        # Strip our previous injection
        before = current_css[:current_css.index(marker_start)].rstrip()
        after_marker = current_css[current_css.index(marker_start):]
        # Find the end of our block (next non-our-CSS or end)
        lines = after_marker.split("\n")
        end_idx = len(lines)
        for i, line in enumerate(lines):
            if i > 0 and line.strip() and not line.startswith(".dashboard-chart-id-1") and not line.startswith("/*") and not line.startswith(" ") and not line.startswith("}"):
                end_idx = i
                break
        remaining = "\n".join(lines[end_idx:]).strip()
        current_css = (before + "\n" + remaining).strip()

    new_css = (current_css + "\n\n" + css).strip() if current_css else css

    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {"css": new_css})
    print(f"  [~] Dashboard CSS injected for gauge chart", file=sys.stderr)


def fix_gauge_layout(api):
    """Make the gauge card smaller (less wasted vertical space)."""
    data = api.get(f"/api/v1/dashboard/{DASHBOARD_ID}")
    position = json.loads(data["result"]["position_json"])

    # Set gauge to a tighter height — semicircle needs less vertical space
    if "CHART-1" in position:
        position["CHART-1"]["meta"]["width"] = 12
        position["CHART-1"]["meta"]["height"] = 40  # down from 55

    api.put(f"/api/v1/dashboard/{DASHBOARD_ID}", {
        "position_json": json.dumps(position),
    })
    print(f"  [~] Gauge layout: width=12, height=40", file=sys.stderr)


def main():
    print("=" * 60, file=sys.stderr)
    print("Fixing gauge appearance", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    print("\n[1/3] Optimizing gauge chart params...", file=sys.stderr)
    fix_gauge_params(api)

    print("\n[2/3] Injecting dashboard CSS...", file=sys.stderr)
    inject_gauge_css(api)

    print("\n[3/3] Adjusting gauge layout size...", file=sys.stderr)
    fix_gauge_layout(api)

    print(f"\n Done! Check: {SUPERSET_URL}/superset/dashboard/{DASHBOARD_ID}/", file=sys.stderr)


if __name__ == "__main__":
    main()
