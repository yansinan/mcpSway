#!/usr/bin/env python3
"""sway-tree-parser — Parse sway IPC tree and print human-readable layout.

Works without jq. Reads swaymsg -t get_tree --raw output directly.
Usage:
  python3 sway-tree-parser.py              # Live query
  python3 sway-tree-parser.py dump.json    # From saved file
"""

import json
import subprocess
import sys
from pathlib import Path


def get_tree(source: str | None = None) -> dict:
    """Get the sway tree from a live session or a saved JSON file."""
    if source is None:
        return json.loads(
            subprocess.check_output(
                ["swaymsg", "-t", "get_tree", "--raw"], timeout=5
            )
        )
    return json.loads(Path(source).read_text())


def get_outputs(tree: dict) -> list[dict]:
    """Get outputs from the tree."""
    return [n for n in tree.get("nodes", []) if n.get("type") == "output"]


def get_workspaces(output: dict) -> list[dict]:
    """Get workspaces within an output."""
    return [n for n in output.get("nodes", []) if n.get("type") == "workspace"]


def get_applications(workspace: dict) -> list[dict]:
    """Recursively find all application containers in a workspace.
    
    Returns list of dicts with: app_id, pid, layout, rect, title, shell,
    window_properties, workspace, depth, children (recurse).
    """

    def walk(node, depth=0) -> list[dict]:
        results = []
        # A container is an "application" if it has app_id or window_properties.class
        app_id = node.get("app_id") or (node.get("window_properties") or {}).get("class")
        if app_id:
            results.append({
                "app_id": app_id,
                "pid": node.get("pid"),
                "layout": node.get("layout"),
                "rect": node.get("rect"),
                "title": node.get("name", ""),
                "shell": node.get("shell"),
                "window_properties": node.get("window_properties"),
                "workspace": node.get("workspace"),
                "depth": depth,
                "type": node.get("type"),
            })
        for child in node.get("nodes", []):
            results.extend(walk(child, depth + 1))
        # Also walk floating nodes
        for child in node.get("floating_nodes", []):
            results.extend(walk(child, depth + 1))
        return results

    return walk(workspace)


def get_container_tree(node, indent=0) -> str:
    """Build a tree-text representation of the node structure."""
    prefix = "  " * indent
    t = node.get("type", "?")
    lines = []

    if t == "output":
        name = node.get("name", "?")
        lines.append(f"{prefix}[Output] {name}")
    elif t == "workspace":
        name = node.get("name", "?")
        layout = node.get("layout", "?")
        fs = node.get("fullscreen_mode", 0)
        lines.append(f"{prefix}[WS] {name}  layout={layout}  fullscreen={fs}")
    elif t == "con":
        app_id = node.get("app_id") or (node.get("window_properties") or {}).get("class") or "?"
        layout = node.get("layout") or "none"
        pid = node.get("pid")
        rect = node.get("rect", {})
        title = node.get("name", "")
        if title:
            title = title[:60]
        lines.append(
            f"{prefix}[Con] {app_id}  layout={layout}  pid={pid}"
        )
        if title:
            lines.append(f"{prefix}       title: {title}")
    else:
        lines.append(f"{prefix}[{t}]")

    for child in node.get("nodes", []):
        lines.extend(get_container_tree(child, indent + 1))
    for child in node.get("floating_nodes", []):
        lines.extend(get_container_tree(child, indent + 1))

    return "\n".join(lines)


def get_launch_commands(apps: list[dict]) -> dict:
    """Read /proc/PID/cmdline for each unique PID to get launch commands."""
    cmds = {}
    for app in apps:
        pid = app.get("pid")
        if pid and pid not in cmds:
            try:
                with open(f"/proc/{pid}/cmdline") as f:
                    raw = f.read()
                cmds[pid] = raw.replace("\0", " ").strip()
            except (FileNotFoundError, PermissionError):
                cmds[pid] = "[permission denied]"
    return cmds


def print_outputs(tree: dict):
    """Print output list (monitors)."""
    outputs = []
    for n in tree.get("nodes", []):
        if n.get("type") == "output" and n.get("name", "").startswith("__"):
            continue  # skip __i3 scratch
        if n.get("type") == "output":
            r = n.get("rect", {})
            outputs.append(
                f"  {n['name']}: {n.get('make','')} {n.get('model','')} — "
                f"ws={n.get('current_workspace','?')}  "
                f"rect=({r.get('x')},{r.get('y')}) {r.get('width')}x{r.get('height')}"
            )
    print("Outputs:")
    for o in outputs:
        print(o)
    print()


def print_workspace_apps(tree: dict):
    """Print each workspace with its apps and launch commands."""
    for output in get_outputs(tree):
        if output.get("name", "").startswith("__"):
            continue
        print(f"--- {output['name']} ---")

        for ws in get_workspaces(output):
            apps = get_applications(ws)
            cmds = get_launch_commands(apps)

            print(f"\nWS {ws['name']} (layout={ws.get('layout')})")
            if ws.get("representation"):
                print(f"  Repr: {ws['representation']}")

            # Unique PIDs with their first app context
            seen_pids = {}
            for app in apps:
                pid = app.get("pid")
                if pid and pid not in seen_pids:
                    seen_pids[pid] = app

            for pid, app in seen_pids.items():
                cmd = cmds.get(pid, "?")
                print(f"  PID {pid:>6}  {app['app_id']:<30}  {cmd[:100]}")
                if "window_properties" in app and app.get("window_properties"):
                    wp = app["window_properties"]
                    if wp.get("window_role"):
                        print(f"                 role={wp['window_role']}")

            if not seen_pids:
                print("  (no application windows)")


def print_container_tree(tree: dict):
    """Print full tree structure."""
    print("Container tree:")
    for node in tree.get("nodes", []):
        if node.get("name") == "__i3":
            continue
        print(get_container_tree(node))


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else None
    tree = get_tree(source)

    print_outputs(tree)
    print_workspace_apps(tree)
    print()
    print_container_tree(tree)
