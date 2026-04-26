#!/usr/bin/env python3
"""
Superset Dashboard Tool
========================
A toolbox for Claude (or humans) to interact with the Superset API.
Subcommands handle discrete steps; Claude orchestrates the workflow.

Usage:
    export SUPERSET_URL=http://3.76.235.192:8088
    export SUPERSET_ADMIN_USERNAME=admin
    export SUPERSET_ADMIN_PASSWORD=yourpassword

    # Step 1: List datasets
    python3 scripts/create_dashboard.py list-datasets

    # Step 2: Inspect dataset structure (JSON output for Claude)
    python3 scripts/create_dashboard.py describe-dataset 1

    # Step 3: Create dashboard from a config JSON that Claude generates
    python3 scripts/create_dashboard.py create --config dashboard_config.json

    # Utility: Delete a dashboard (and optionally its charts)
    python3 scripts/create_dashboard.py delete-dashboard 42 --delete-charts
"""

import argparse
import json
import os
import sys
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

SUPERSET_URL = os.getenv("SUPERSET_URL", "http://3.76.235.192:8088").rstrip("/")
USERNAME = os.getenv("SUPERSET_ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("SUPERSET_ADMIN_PASSWORD", "")


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------
class SupersetAPI:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.session = requests.Session()
        self._login(username, password)
        self._get_csrf_token()

    def _login(self, username, password):
        r = self.session.post(
            f"{self.base_url}/api/v1/security/login",
            json={"username": username, "password": password, "provider": "db"},
        )
        r.raise_for_status()
        token = r.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _get_csrf_token(self):
        r = self.session.get(f"{self.base_url}/api/v1/security/csrf_token/")
        r.raise_for_status()
        csrf = r.json()["result"]
        self.session.headers.update({"X-CSRFToken": csrf})

    def get(self, endpoint, **kwargs):
        r = self.session.get(f"{self.base_url}{endpoint}", **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, endpoint, payload):
        r = self.session.post(
            f"{self.base_url}{endpoint}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if not r.ok:
            print(json.dumps({"error": r.status_code, "detail": r.text[:500]}))
            r.raise_for_status()
        return r.json()

    def put(self, endpoint, payload):
        r = self.session.put(
            f"{self.base_url}{endpoint}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if not r.ok:
            print(json.dumps({"error": r.status_code, "detail": r.text[:500]}))
            r.raise_for_status()
        return r.json()

    def delete(self, endpoint):
        r = self.session.delete(f"{self.base_url}{endpoint}")
        r.raise_for_status()
        return r.json() if r.text else {}


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
TYPE_MAP = {0: "STRING", 1: "NUMERIC", 2: "TEMPORAL", 3: "BOOLEAN"}


def cmd_list_datasets(api, args):
    """List all datasets as JSON."""
    data = api.get("/api/v1/dataset/", params={"q": "(page_size:100)"})
    datasets = []
    for ds in data.get("result", []):
        datasets.append({
            "id": ds["id"],
            "table_name": ds["table_name"],
            "database": ds.get("database", {}).get("database_name", "?"),
            "schema": ds.get("schema", ""),
        })
    print(json.dumps(datasets, indent=2))


def cmd_describe_dataset(api, args):
    """Output dataset structure as JSON — columns, types, metrics."""
    data = api.get(f"/api/v1/dataset/{args.dataset_id}")
    result = data["result"]
    output = {
        "dataset_id": args.dataset_id,
        "table_name": result.get("table_name"),
        "database": result.get("database", {}).get("database_name", "?"),
        "schema": result.get("schema", ""),
        "columns": [],
        "metrics": [],
    }
    for c in sorted(result.get("columns", []), key=lambda x: x.get("column_name", "")):
        output["columns"].append({
            "column_name": c["column_name"],
            "type": c.get("type", ""),
            "generic_type": TYPE_MAP.get(c.get("type_generic"), "UNKNOWN"),
            "is_temporal": c.get("is_dttm", False),
            "filterable": c.get("filterable", True),
            "groupby": c.get("groupby", True),
        })
    for m in result.get("metrics", []):
        output["metrics"].append({
            "metric_name": m["metric_name"],
            "expression": m.get("expression", ""),
            "verbose_name": m.get("verbose_name", ""),
        })
    print(json.dumps(output, indent=2))


def cmd_create(api, args):
    """
    Create a dashboard from a JSON config file.

    Expected config format:
    {
      "dashboard_title": "My Dashboard",
      "dataset_id": 1,
      "default_filters": [
        {
          "column": "region",
          "type": "filter_select",         # filter_select, filter_range, filter_time, filter_timecolumn, filter_timegrain
          "default_value": ["US", "EU"],    # optional — pre-selected values
          "multiple": true                  # optional, default true
        }
      ],
      "charts": [
        {
          "name": "Total Revenue",
          "viz_type": "big_number_total",
          "width": 4,                       # grid units out of 12
          "height": 30,                     # pixel units
          "params": { ... }                 # full viz params
        }
      ],
      "layout": "auto"  # "auto" or explicit position_json
    }
    """
    with open(args.config) as f:
        config = json.load(f)

    dataset_id = config["dataset_id"]
    ds_uid = f"{dataset_id}__table"
    title = config["dashboard_title"]

    # --- Step 1: Create empty dashboard first ---
    dash_payload = {
        "dashboard_title": title,
        "published": True,
    }
    result = api.post("/api/v1/dashboard/", dash_payload)
    dash_id = result["id"]
    print(f"[+] Dashboard #{dash_id} created: {title}", file=sys.stderr)

    # --- Step 2: Collect all chart definitions (flat or tabbed) ---
    all_chart_defs = []
    tab_defs = config.get("tabs")
    if tab_defs:
        for tab in tab_defs:
            all_chart_defs.extend(tab["charts"])
    else:
        all_chart_defs = config.get("charts", [])

    # --- Step 3: Create charts linked to the dashboard ---
    created_charts = []
    chart_id_by_index = {}  # index -> chart_id for tab mapping
    for idx, chart_def in enumerate(all_chart_defs):
        params = chart_def["params"]
        params.setdefault("datasource", ds_uid)
        params.setdefault("viz_type", chart_def["viz_type"])

        payload = {
            "slice_name": chart_def["name"],
            "viz_type": chart_def["viz_type"],
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps(params),
            "dashboards": [dash_id],
        }
        result = api.post("/api/v1/chart/", payload)
        chart_id = result["id"]
        chart_id_by_index[idx] = chart_id
        created_charts.append({
            "chart_id": chart_id,
            "name": chart_def["name"],
            "viz_type": chart_def["viz_type"],
            "width": chart_def.get("width", 6),
            "height": chart_def.get("height", 50),
            "row": chart_def.get("row"),
        })
        print(f"[+] Chart #{chart_id}: {chart_def['name']} ({chart_def['viz_type']})", file=sys.stderr)

    # --- Step 4: Build layout ---
    tabs_layout = None
    if tab_defs:
        offset = 0
        tabs_layout = []
        for tab in tab_defs:
            tab_chart_ids = [chart_id_by_index[offset + i] for i in range(len(tab["charts"]))]
            tabs_layout.append({"title": tab["title"], "chart_ids": tab_chart_ids})
            offset += len(tab["charts"])

    if config.get("layout") == "auto" or "layout" not in config:
        position = build_auto_layout(created_charts, tabs=tabs_layout)
    else:
        position = config["layout"]

    # --- Step 4: Resolve exclude-based filter defaults ---
    for filt in config.get("default_filters", []):
        if "default_value_exclude" in filt and filt.get("type") == "filter_select":
            exclude = set(filt["default_value_exclude"])
            col = filt["column"]
            try:
                result_data = api.get(
                    f"/api/v1/dataset/{dataset_id}/column/{col}/values/"
                )
                all_values = [v for v in result_data.get("result", [])]
                filt["default_value"] = [v for v in all_values if v not in exclude]
                print(f"[+] Filter '{col}': resolved {len(all_values)} values, excluded {exclude}", file=sys.stderr)
            except Exception as e:
                print(f"[!] Could not resolve exclude for '{col}': {e}. Filter will have no default.", file=sys.stderr)
            del filt["default_value_exclude"]

    # --- Step 5: Build native filters ---
    native_filters = []
    for i, filt in enumerate(config.get("default_filters", [])):
        filter_id = f"NATIVE_FILTER-{i+1}"
        filter_type = filt.get("type", "filter_select")
        default_value = filt.get("default_value")

        filter_config = {
            "id": filter_id,
            "controlValues": {
                "enableEmptyFilter": False,
                "defaultToFirstItem": False,
                "multiSelect": filt.get("multiple", True),
                "searchAllOptions": False,
                "inverseSelection": False,
            },
            "name": filt.get("label", filt["column"].replace("_", " ").title()),
            "filterType": filter_type,
            "targets": [{"datasetId": dataset_id, "column": {"name": filt["column"]}}],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "type": "NATIVE_FILTER",
        }

        if "controlValues_extra" in filt:
            filter_config["controlValues"].update(filt["controlValues_extra"])

        if default_value is not None:
            if filter_type == "filter_select":
                filter_config["defaultDataMask"] = {
                    "filterState": {"value": default_value if isinstance(default_value, list) else [default_value]},
                }
            elif filter_type == "filter_range":
                filter_config["defaultDataMask"] = {
                    "filterState": {"value": default_value},
                }
            elif filter_type == "filter_time":
                filter_config["defaultDataMask"] = {
                    "filterState": {"value": default_value},
                }

        native_filters.append(filter_config)

    # --- Step 6: Build json_metadata ---
    json_metadata = {
        "native_filter_configuration": native_filters,
        "default_filters": "{}",
        "timed_refresh_immune_slices": [],
        "expanded_slices": {},
        "refresh_frequency": 0,
        "chart_configuration": {},
        "color_scheme": config.get("color_scheme", ""),
        "label_colors": {},
    }

    # --- Step 7: Update dashboard with layout and filters ---
    update_payload = {
        "position_json": json.dumps(position),
        "json_metadata": json.dumps(json_metadata),
    }
    api.put(f"/api/v1/dashboard/{dash_id}", update_payload)
    print(f"[+] Dashboard updated with layout and {len(native_filters)} filters", file=sys.stderr)

    output = {
        "dashboard_id": dash_id,
        "dashboard_url": f"{SUPERSET_URL}/superset/dashboard/{dash_id}/",
        "charts_created": [{"id": c["chart_id"], "name": c["name"]} for c in created_charts],
        "filters_created": len(native_filters),
    }
    print(json.dumps(output, indent=2))


def cmd_list_dashboards(api, args):
    """List all dashboards as JSON."""
    data = api.get("/api/v1/dashboard/", params={"q": "(page_size:100)"})
    dashboards = []
    for d in data.get("result", []):
        dashboards.append({
            "id": d["id"],
            "dashboard_title": d.get("dashboard_title", ""),
            "published": d.get("published", False),
            "changed_on": d.get("changed_on_delta_humanized", ""),
            "status": d.get("status", ""),
        })
    print(json.dumps(dashboards, indent=2))


def cmd_describe_dashboard(api, args):
    """Output full dashboard structure: tabs, charts per tab, filters."""
    data = api.get(f"/api/v1/dashboard/{args.dashboard_id}")
    result = data["result"]

    position = json.loads(result.get("position_json", "{}"))
    metadata = json.loads(result.get("json_metadata", "{}"))

    # Build chart_id -> position meta lookup
    chart_positions = {}
    for key, val in position.items():
        if not isinstance(val, dict):
            continue
        if val.get("type") == "CHART":
            cid = val["meta"]["chartId"]
            chart_positions[cid] = {
                "position_key": key,
                "width": val["meta"].get("width"),
                "height": val["meta"].get("height"),
                "parents": val.get("parents", []),
            }

    # Fetch all charts linked to this dashboard
    chart_details = {}
    chart_list = api.get("/api/v1/chart/", params={
        "q": json.dumps({"filters": [{"col": "dashboards", "opr": "rel_m_m", "value": args.dashboard_id}], "page_size": 200})
    })
    for c in chart_list.get("result", []):
        chart_details[c["id"]] = {
            "id": c["id"],
            "name": c.get("slice_name", ""),
            "viz_type": c.get("viz_type", ""),
        }

    # Parse tab structure
    tabs_output = []
    tab_keys = sorted([k for k in position if isinstance(position[k], dict) and position[k].get("type") == "TAB"],
                       key=lambda k: int(k.split("-")[1]) if k.split("-")[1].isdigit() else 0)

    if tab_keys:
        for tk in tab_keys:
            tab = position[tk]
            tab_info = {"tab_key": tk, "title": tab["meta"].get("text", ""), "rows": []}

            for row_key in tab.get("children", []):
                row_node = position.get(row_key, {})
                row_charts = []
                for chart_key in row_node.get("children", []):
                    chart_node = position.get(chart_key, {})
                    if chart_node.get("type") == "CHART":
                        cid = chart_node["meta"]["chartId"]
                        detail = chart_details.get(cid, {})
                        row_charts.append({
                            "chart_id": cid,
                            "name": detail.get("name", chart_node["meta"].get("sliceName", "")),
                            "viz_type": detail.get("viz_type", ""),
                            "width": chart_node["meta"].get("width"),
                            "height": chart_node["meta"].get("height"),
                        })
                tab_info["rows"].append({"row_key": row_key, "charts": row_charts})

            tabs_output.append(tab_info)

    # Parse filters
    filters_output = []
    for f in metadata.get("native_filter_configuration", []):
        filt = {
            "id": f["id"],
            "name": f["name"],
            "type": f.get("filterType", ""),
            "column": f["targets"][0].get("column", {}).get("name") if f.get("targets") else None,
        }
        dm = f.get("defaultDataMask", {}).get("filterState", {})
        if dm.get("value") is not None:
            filt["default_value"] = dm["value"]
        filters_output.append(filt)

    output = {
        "dashboard_id": args.dashboard_id,
        "title": result.get("dashboard_title", ""),
        "published": result.get("published"),
        "changed_on": result.get("changed_on"),
        "total_charts": len(chart_details),
        "tabs": tabs_output if tabs_output else None,
        "filters": filters_output,
    }

    # If no tabs, list charts flat
    if not tabs_output:
        output["charts"] = list(chart_details.values())

    print(json.dumps(output, indent=2))


def cmd_describe_chart(api, args):
    """Output a single chart's full configuration."""
    data = api.get(f"/api/v1/chart/{args.chart_id}")
    result = data["result"]

    params = {}
    if result.get("params"):
        params = json.loads(result["params"]) if isinstance(result["params"], str) else result["params"]

    output = {
        "chart_id": args.chart_id,
        "name": result.get("slice_name", ""),
        "viz_type": result.get("viz_type", ""),
        "datasource_id": result.get("datasource_id"),
        "datasource_type": result.get("datasource_type"),
        "dashboards": [d["id"] for d in result.get("dashboards", [])],
        "params": params,
    }
    print(json.dumps(output, indent=2))


def cmd_update_chart(api, args):
    """
    Update a chart's params (deep-merged) and/or name.

    Usage:
        # Update params via JSON string
        python3 scripts/create_dashboard.py update-chart 36 --params '{"header_font_size": 0.4}'

        # Update params from a file
        python3 scripts/create_dashboard.py update-chart 36 --params-file patch.json

        # Rename a chart
        python3 scripts/create_dashboard.py update-chart 36 --name "New Name"
    """
    # Fetch current state
    data = api.get(f"/api/v1/chart/{args.chart_id}")
    result = data["result"]
    current_params = json.loads(result["params"]) if isinstance(result.get("params"), str) else (result.get("params") or {})

    payload = {}

    # Merge params
    if args.params or args.params_file:
        if args.params_file:
            with open(args.params_file) as f:
                patch = json.load(f)
        else:
            patch = json.loads(args.params)

        def deep_merge(base, override):
            for k, v in override.items():
                if isinstance(v, dict) and isinstance(base.get(k), dict):
                    deep_merge(base[k], v)
                else:
                    base[k] = v
            return base

        merged = deep_merge(current_params, patch)
        payload["params"] = json.dumps(merged)

    if args.name:
        payload["slice_name"] = args.name

    if not payload:
        print(json.dumps({"error": "Nothing to update. Use --params, --params-file, or --name."}))
        sys.exit(1)

    api.put(f"/api/v1/chart/{args.chart_id}", payload)
    print(f"[+] Chart #{args.chart_id} updated", file=sys.stderr)

    # Print new state
    updated = api.get(f"/api/v1/chart/{args.chart_id}")
    new_params = json.loads(updated["result"]["params"]) if isinstance(updated["result"].get("params"), str) else {}
    print(json.dumps({
        "chart_id": args.chart_id,
        "name": updated["result"].get("slice_name", ""),
        "params": new_params,
    }, indent=2))


def cmd_update_layout(api, args):
    """
    Update chart sizes in the dashboard layout.

    Usage:
        # Resize specific charts (JSON: {chart_id: {width, height}})
        python3 scripts/create_dashboard.py update-layout 5 --resize '{"36": {"height": 20}, "37": {"height": 20}}'
    """
    data = api.get(f"/api/v1/dashboard/{args.dashboard_id}")
    position = json.loads(data["result"].get("position_json", "{}"))

    resize_map = json.loads(args.resize) if args.resize else {}

    updated = []
    for key, val in position.items():
        if not isinstance(val, dict) or val.get("type") != "CHART":
            continue
        cid = str(val["meta"]["chartId"])
        if cid in resize_map:
            for prop in ("width", "height"):
                if prop in resize_map[cid]:
                    val["meta"][prop] = resize_map[cid][prop]
            updated.append(cid)

    if not updated:
        print(json.dumps({"error": "No matching charts found in layout"}))
        sys.exit(1)

    api.put(f"/api/v1/dashboard/{args.dashboard_id}", {"position_json": json.dumps(position)})
    print(f"[+] Dashboard #{args.dashboard_id}: resized charts {updated}", file=sys.stderr)
    print(json.dumps({"updated_charts": updated}))


def cmd_delete_dashboard(api, args):
    """Delete a dashboard and optionally its charts."""
    if args.delete_charts:
        data = api.get(f"/api/v1/dashboard/{args.dashboard_id}")
        slices = data.get("result", {}).get("slices", [])
        for s in slices:
            api.delete(f"/api/v1/chart/{s['slice_id']}")
            print(f"[+] Deleted chart #{s['slice_id']}: {s.get('slice_name', '?')}", file=sys.stderr)

    api.delete(f"/api/v1/dashboard/{args.dashboard_id}")
    print(json.dumps({"deleted": args.dashboard_id}))


# ---------------------------------------------------------------------------
# Layout builder
# ---------------------------------------------------------------------------
def build_auto_layout(charts, tabs=None):
    """
    Build a grid layout respecting the 'row' field on each chart.
    Charts with the same 'row' value are placed side-by-side.
    If no 'row' field, falls back to sequential placement.

    When `tabs` is provided, wraps charts into TABS/TAB components.
    `tabs` is a list of {"title": str, "chart_ids": [int, ...]}.
    """
    from collections import OrderedDict

    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": ""}},
        "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"]},
        "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": []},
    }

    chart_lookup = {c["chart_id"]: c for c in charts}

    if tabs:
        tabs_id = "TABS-1"
        position[tabs_id] = {
            "id": tabs_id, "type": "TABS", "children": [],
            "parents": ["ROOT_ID", "GRID_ID"],
        }
        position["GRID_ID"]["children"].append(tabs_id)

        global_row_counter = 0

        for tab_idx, tab_def in enumerate(tabs, start=1):
            tab_id = f"TAB-{tab_idx}"
            position[tabs_id]["children"].append(tab_id)
            position[tab_id] = {
                "id": tab_id, "type": "TAB", "children": [],
                "parents": ["ROOT_ID", "GRID_ID", tabs_id],
                "meta": {"text": tab_def["title"], "defaultText": f"Tab {tab_idx}"},
            }

            # Group this tab's charts by row
            tab_charts = [chart_lookup[cid] for cid in tab_def["chart_ids"] if cid in chart_lookup]
            rows = OrderedDict()
            for idx, c in enumerate(tab_charts):
                row_num = c.get("row", idx + 100)
                rows.setdefault(row_num, []).append(c)

            for row_num, row_charts in rows.items():
                global_row_counter += 1
                row_id = f"ROW-{global_row_counter}"
                row_children = []

                for c in row_charts:
                    cid = f"CHART-{c['chart_id']}"
                    row_children.append(cid)
                    position[cid] = {
                        "id": cid, "type": "CHART", "children": [],
                        "parents": ["ROOT_ID", "GRID_ID", tabs_id, tab_id, row_id],
                        "meta": {
                            "chartId": c["chart_id"],
                            "height": c.get("height", 50),
                            "sliceName": c["name"],
                            "width": c.get("width", 12 // len(row_charts)),
                        },
                    }

                position[row_id] = {
                    "id": row_id, "type": "ROW", "children": row_children,
                    "parents": ["ROOT_ID", "GRID_ID", tabs_id, tab_id],
                    "meta": {"background": "BACKGROUND_TRANSPARENT"},
                }
                position[tab_id]["children"].append(row_id)

        return position

    # --- Flat layout (no tabs) ---
    rows = OrderedDict()
    for idx, c in enumerate(charts):
        row_num = c.get("row", idx + 100)
        rows.setdefault(row_num, []).append(c)

    for row_idx, (row_num, row_charts) in enumerate(rows.items(), start=1):
        row_id = f"ROW-{row_idx}"
        row_children = []

        for c in row_charts:
            cid = f"CHART-{c['chart_id']}"
            row_children.append(cid)
            position[cid] = {
                "id": cid, "type": "CHART", "children": [],
                "parents": ["ROOT_ID", "GRID_ID", row_id],
                "meta": {
                    "chartId": c["chart_id"],
                    "height": c.get("height", 50),
                    "sliceName": c["name"],
                    "width": c.get("width", 12 // len(row_charts)),
                },
            }

        position[row_id] = {
            "id": row_id, "type": "ROW", "children": row_children,
            "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        position["GRID_ID"]["children"].append(row_id)

    return position


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Superset Dashboard Tool")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-datasets", help="List all datasets (JSON)")
    sub.add_parser("list-dashboards", help="List all dashboards (JSON)")

    p_desc = sub.add_parser("describe-dataset", help="Describe dataset columns/metrics (JSON)")
    p_desc.add_argument("dataset_id", type=int)

    p_desc_dash = sub.add_parser("describe-dashboard", help="Describe dashboard structure: tabs, charts, filters (JSON)")
    p_desc_dash.add_argument("dashboard_id", type=int)

    p_desc_chart = sub.add_parser("describe-chart", help="Describe a single chart's full params (JSON)")
    p_desc_chart.add_argument("chart_id", type=int)

    p_create = sub.add_parser("create", help="Create dashboard from config JSON")
    p_create.add_argument("--config", required=True, help="Path to dashboard config JSON")

    p_upd_chart = sub.add_parser("update-chart", help="Update chart params and/or name")
    p_upd_chart.add_argument("chart_id", type=int)
    p_upd_chart.add_argument("--params", help="JSON string of params to deep-merge")
    p_upd_chart.add_argument("--params-file", help="Path to JSON file with params to deep-merge")
    p_upd_chart.add_argument("--name", help="New chart name")

    p_upd_layout = sub.add_parser("update-layout", help="Resize charts in dashboard layout")
    p_upd_layout.add_argument("dashboard_id", type=int)
    p_upd_layout.add_argument("--resize", help='JSON: {"chart_id": {"width": N, "height": N}}')

    p_del = sub.add_parser("delete-dashboard", help="Delete a dashboard")
    p_del.add_argument("dashboard_id", type=int)
    p_del.add_argument("--delete-charts", action="store_true", help="Also delete associated charts")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not PASSWORD:
        print(json.dumps({"error": "SUPERSET_ADMIN_PASSWORD not set"}))
        sys.exit(1)

    api = SupersetAPI(SUPERSET_URL, USERNAME, PASSWORD)

    if args.command == "list-datasets":
        cmd_list_datasets(api, args)
    elif args.command == "list-dashboards":
        cmd_list_dashboards(api, args)
    elif args.command == "describe-dataset":
        cmd_describe_dataset(api, args)
    elif args.command == "describe-dashboard":
        cmd_describe_dashboard(api, args)
    elif args.command == "describe-chart":
        cmd_describe_chart(api, args)
    elif args.command == "create":
        cmd_create(api, args)
    elif args.command == "update-chart":
        cmd_update_chart(api, args)
    elif args.command == "update-layout":
        cmd_update_layout(api, args)
    elif args.command == "delete-dashboard":
        cmd_delete_dashboard(api, args)


if __name__ == "__main__":
    main()
