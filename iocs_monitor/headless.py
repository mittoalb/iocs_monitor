"""Headless (non-Flask) API for iocs_monitor.

Same operations as the Flask REST endpoints (/status, /start, /stop,
/medm, /gui) — but callable in-process without launching the web
server. Used by `iom-cli` and by any AI agent that wants to query
or control IOCs without HTTP.

The Flask app (`iocs_server.py`) is unchanged; it continues to serve
the browser UI on port 5100. This module duplicates a small amount
of logic on purpose — cheaper than refactoring the working server."""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Dict, List, Optional

import requests


# ── config ──────────────────────────────────────────────────────────

def _config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "config.json")


def load_config() -> Dict:
    """Read the packaged `config.json` and return the raw dict.
    Same file the Flask server reads."""
    with open(_config_path()) as f:
        return json.load(f)


def _iocs_flat_and_categorized(cfg: Dict):
    """Normalize the config into a flat `{ioc_name: {"script","description","category"}}`
    dict and a categorized `{category: {ioc_name: {...}}}` dict. Handles
    both legacy string values and the current dict-with-script format."""
    flat: Dict[str, Dict[str, str]] = {}
    categorized: Dict[str, Dict[str, Dict[str, str]]] = {}
    for key, value in cfg.items():
        if key in ("paths", "excluded", "beamline_guis"):
            continue
        if not isinstance(value, dict):
            continue
        cat: Dict[str, Dict[str, str]] = {}
        for ioc_name, ioc_data in value.items():
            if isinstance(ioc_data, str):
                entry = {"script": ioc_data, "description": "",
                         "category": key}
            else:
                entry = {"script": ioc_data.get("script", ""),
                         "description": ioc_data.get("description", ""),
                         "category": key}
            flat[ioc_name] = entry
            cat[ioc_name] = entry
        categorized[key] = cat
    return flat, categorized


def _scripts_dir(cfg: Dict) -> str:
    return cfg["paths"]["scripts_dir"]


def _cgi_url(cfg: Dict) -> str:
    return cfg["paths"]["CGI_URL"]


# ── enumeration ─────────────────────────────────────────────────────

def list_iocs(category: Optional[str] = None) -> List[Dict]:
    """Return every IOC in the config as a flat list. Each entry:
    `{"name", "script", "description", "category", "is_gui"}`. Pass
    `category="TXM"` (etc.) to filter to a single group."""
    cfg = load_config()
    flat, _ = _iocs_flat_and_categorized(cfg)
    guis = set(cfg.get("beamline_guis", []))
    out = []
    for name, data in flat.items():
        if category is not None and data["category"] != category:
            continue
        out.append({
            "name":        name,
            "script":      data["script"],
            "description": data["description"],
            "category":    data["category"],
            "is_gui":      name in guis,
        })
    return out


def list_categories() -> List[str]:
    """Every category key defined in the config (in file order)."""
    cfg = load_config()
    return [k for k in cfg
            if k not in ("paths", "excluded", "beamline_guis")
            and isinstance(cfg[k], dict)]


# ── status ──────────────────────────────────────────────────────────

def _clean_js_array(js_array_str: str) -> str:
    js_array_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
                          r'\1"\2":', js_array_str)
    js_array_str = re.sub(r",\s*([}\]])", r"\1", js_array_str)
    return js_array_str


def get_status(ioc: str, timeout: float = 5.0) -> Dict:
    """Return the current status + address for an IOC. Same logic as
    the Flask `/status/<ioc>` endpoint — scrapes the CGI page listed
    in config, greps the JS array for the IOC entry.

    Shape: `{"status": <str>, "address": <str>}`. Status is `"GUI"`
    for beamline-GUI entries, `"unavailable"` / `"not found"` if the
    scrape fails, or the value the CGI reports (`"up"`, `"down"`,
    etc.)."""
    cfg = load_config()
    guis = set(cfg.get("beamline_guis", []))
    if ioc in guis:
        return {"status": "GUI", "address": "N/A"}
    try:
        html = requests.get(_cgi_url(cfg), timeout=timeout).text
        match = re.search(r"var\s+iocs\s*=\s*(\[[\s\S]*?\])\s*;", html)
        if not match:
            return {"status": "unavailable", "address": "N/A"}
        raw_array = match.group(1)
        json_compatible = _clean_js_array(raw_array)
        ioc_data = json.loads(json_compatible)
        for entry in ioc_data:
            if entry["name"] == ioc:
                address = (".".join(entry["address"])
                           if isinstance(entry["address"], list)
                           else str(entry["address"]))
                return {"status": entry["status"], "address": address}
        return {"status": "not found", "address": "N/A"}
    except Exception as e:
        return {"status": f"error: {e}", "address": "N/A"}


# ── control (start / stop / medm / gui) ─────────────────────────────

def _run_script(ioc: str, action: Optional[str]) -> Dict:
    """Invoke `<scripts_dir>/<script>.sh [action]` for the named
    IOC. Returns `{"ok": True, "script": <path>}` on submit success,
    or `{"error": <msg>}` on failure. `action=None` for GUI launch
    (no argument to the script)."""
    cfg = load_config()
    flat, _ = _iocs_flat_and_categorized(cfg)
    entry = flat.get(ioc)
    if not entry:
        return {"error": f"Unknown IOC: {ioc}"}
    script_path = os.path.join(_scripts_dir(cfg),
                               f"{entry['script']}.sh")
    if not os.path.isfile(script_path):
        return {"error": f"Script not found: {script_path}"}
    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":1"
    args = [script_path] if action is None else [script_path, action]
    try:
        subprocess.Popen(args, env=env, start_new_session=True)
        return {"ok": True, "script": script_path,
                "action": action or "gui"}
    except Exception as e:
        return {"error": f"Failed to run script: {e}"}


def start_ioc(ioc: str) -> Dict:
    """Fire the `start` action on the IOC's script."""
    return _run_script(ioc, "start")


def stop_ioc(ioc: str) -> Dict:
    """Fire the `stop` action on the IOC's script."""
    return _run_script(ioc, "stop")


def restart_ioc(ioc: str) -> Dict:
    """Convenience wrapper: stop, then start. Returns the start
    result (which is what tells you whether the (re)start submitted).
    The scripts themselves handle whatever settle-time they need."""
    stop = _run_script(ioc, "stop")
    if "error" in stop:
        return stop
    return _run_script(ioc, "start")


def medm(ioc: str) -> Dict:
    """Launch the IOC's MEDM display via its script."""
    return _run_script(ioc, "medm")


def start_gui(ioc: str) -> Dict:
    """Launch a beamline-GUI-style entry (script invoked with no
    arg). Falls through to `_run_script` — same as `/gui/<ioc>` in
    the Flask server."""
    return _run_script(ioc, None)


__all__ = [
    "load_config",
    "list_iocs", "list_categories",
    "get_status",
    "start_ioc", "stop_ioc", "restart_ioc", "medm", "start_gui",
]
