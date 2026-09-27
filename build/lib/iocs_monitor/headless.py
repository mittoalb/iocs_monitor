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
import shlex
import subprocess
import time
from typing import Dict, List, Optional, Tuple

import requests


# ── SSH failure cache ───────────────────────────────────────────────
#
# `gauss` (and any other IOC host) will start returning
# "Connection closed by <ip> port 22" when its sshd MaxStartups /
# fail2ban thresholds are hit. With the browser polling every 5s
# and multiple IOCs on the same host, a single failing account can
# generate dozens of SSH attempts per minute per host — enough to
# lock us out even if the credentials would otherwise work.
#
# So: cache SSH failures per host for a short TTL. First failure is
# a real probe; subsequent probes for the same host within the TTL
# return the cached error instantly, without opening a socket. TTL
# is bypassed by clear_ssh_failure_cache() (useful for tests).
_SSH_FAIL_TTL_SEC = 30.0
_ssh_fail_cache: Dict[str, Tuple[float, str]] = {}   # host -> (expire_at, error_msg)


def _ssh_cached_failure(host: str) -> Optional[str]:
    """If `host` had a recent SSH failure, return the cached error
    message; else None."""
    entry = _ssh_fail_cache.get(host)
    if not entry:
        return None
    expire_at, msg = entry
    if time.monotonic() >= expire_at:
        _ssh_fail_cache.pop(host, None)
        return None
    return msg


def _ssh_record_failure(host: str, msg: str) -> None:
    _ssh_fail_cache[host] = (time.monotonic() + _SSH_FAIL_TTL_SEC, msg)


def _ssh_clear_success(host: str) -> None:
    _ssh_fail_cache.pop(host, None)


def clear_ssh_failure_cache() -> None:
    """Wipe all cached SSH failures. Call after fixing keys or when
    you know the remote is back — otherwise entries just expire on
    their own after ~30 seconds."""
    _ssh_fail_cache.clear()


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


# ── script metadata parsing ─────────────────────────────────────────

# Match  VARNAME="value"  at the start of a line. Only quoted strings
# to keep the parse deterministic; every real script quotes them.
_SCRIPT_VAR_RE = re.compile(
    r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"([^"]*)"\s*$',
    re.MULTILINE,
)

# Interesting shell variables to lift out of a script.
_INTERESTING = (
    "REMOTE_USER", "REMOTE_HOST", "BASE_DIR", "WORK_DIR",
    "SCRIPT_NAME", "IOC_NAME", "HOME_DIR", "CONDA_ENV",
    "CONDA_PATH", "APP_NAME",
)


def _parse_script(script_path: str) -> Dict[str, str]:
    """Extract the top-level shell variables from an IOC control
    script. Returns a dict like:
        {"REMOTE_USER": "usertxm", "REMOTE_HOST": "txm4",
         "WORK_DIR": "/net/.../softioc", "SCRIPT_NAME": "32idbTXM.pl", ...}

    Handles `${VAR}` substitution against previously-parsed variables
    (single-pass, which is enough for the current script style)."""
    result: Dict[str, str] = {}
    try:
        with open(script_path) as f:
            text = f.read()
    except OSError:
        return result

    for m in _SCRIPT_VAR_RE.finditer(text):
        key, raw = m.group(1), m.group(2)
        if key not in _INTERESTING:
            continue
        # Expand ${VAR} using variables we've already seen. Anything
        # unknown is left as-is; we only need the paths good enough
        # for `cd`.
        def _sub(match):
            name = match.group(1)
            return result.get(name, match.group(0))
        expanded = re.sub(r'\$\{([A-Z_][A-Z0-9_]*)\}', _sub, raw)
        expanded = re.sub(r'\$([A-Z_][A-Z0-9_]*)', _sub, expanded)
        result[key] = expanded
    return result


# ── status ──────────────────────────────────────────────────────────

def _clean_js_array(js_array_str: str) -> str:
    js_array_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
                          r'\1"\2":', js_array_str)
    js_array_str = re.sub(r",\s*([}\]])", r"\1", js_array_str)
    return js_array_str


def _ssh_run(user: str, host: str, remote_cmd: str,
             timeout: float = 8.0) -> Tuple[int, str, str]:
    """Run `remote_cmd` on `user@host` via SSH. Returns
    `(returncode, stdout, stderr)`. `returncode == -1` for network
    or timeout failures (stderr carries the reason)."""
    ssh_args = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=3",
        f"{user}@{host}",
        remote_cmd,
    ]
    try:
        proc = subprocess.run(
            ssh_args, capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"ssh timeout after {timeout}s"
    except FileNotFoundError:
        return -1, "", "ssh binary not found"
    except Exception as e:
        return -1, "", str(e)


def _classify_status_output(text: str, rc: int) -> str:
    """Turn the remote `./script status` output into one of our
    canonical status strings."""
    lower = text.lower()
    # "is not running" must be checked before "is running" (substring).
    if "is not running" in lower or "not running" in lower \
            or "is stopped" in lower or "no such process" in lower:
        return "down"
    if "is running" in lower or "already running" in lower:
        return "up"
    if "__status_failed__" in lower:
        return "unavailable"
    if rc == 0:
        # Script exited cleanly with no phrase we recognize. Trust it
        # as "up" only if there's non-empty output; otherwise unknown.
        return "up" if text.strip() else "unknown"
    return f"error (rc={rc})"


def _is_procserver_style(script_name: str) -> bool:
    """True for the classic EPICS status script (`.pl` / `.sh`
    supporting a `status` subcommand). Python entry scripts don't
    match — those are the tomoscan-style start scripts and need the
    pgrep-on-APP_NAME probe instead."""
    return script_name.endswith(".pl") or script_name.endswith(".sh")


def get_status_direct(ioc: str, timeout: float = 8.0) -> Dict:
    """Check IOC status directly on the target host over SSH — no CGI
    scraping. Uses one of two probe styles depending on the script:

      1. **procServer-style** (SCRIPT_NAME is `.pl` / `.sh`, as with
         `32idbTXM.pl`): runs `./<SCRIPT_NAME> status` in `WORK_DIR`
         and greps for `is running`.
      2. **App-process style** (SCRIPT_NAME is a Python file that
         starts the IOC, as with `32idTomoScan.sh` → `start_tomoscan.py`
         + `APP_NAME=tomoScanApp`): runs `pgrep -f APP_NAME` on the
         remote to see if the IOC binary is up.

    Shape: `{"status": <str>, "host": <str>, "address": <str>}`.
    `status` is one of `"up"`, `"down"`, `"GUI"`, `"unavailable"`,
    `"unknown"`, or `"error: ..."`. `address` is set to `host` for
    parity with the CGI-based `get_status`, so callers can consume
    either interchangeably."""
    cfg = load_config()
    flat, _ = _iocs_flat_and_categorized(cfg)
    guis = set(cfg.get("beamline_guis", []))

    if ioc in guis:
        return {"status": "GUI", "host": "N/A", "address": "N/A"}

    entry = flat.get(ioc)
    if not entry:
        return {"status": "not found", "host": "N/A", "address": "N/A"}

    script_path = os.path.join(_scripts_dir(cfg), f"{entry['script']}.sh")
    if not os.path.isfile(script_path):
        return {"status": f"error: script not found: {script_path}",
                "host": "N/A", "address": "N/A"}

    meta = _parse_script(script_path)
    host = meta.get("REMOTE_HOST")
    user = meta.get("REMOTE_USER")
    work_dir = meta.get("WORK_DIR")
    script_name = meta.get("SCRIPT_NAME")
    app_name = meta.get("APP_NAME")

    # Need at least host + user + one probe strategy.
    if not (host and user):
        return {"status": "error: script missing REMOTE_HOST/USER",
                "host": host or "N/A", "address": host or "N/A"}

    use_procserver = (script_name and work_dir
                      and _is_procserver_style(script_name))
    use_pgrep = bool(app_name) and not use_procserver

    if not (use_procserver or use_pgrep):
        # Fell through — probably a compound / GUI wrapper script that
        # can't be probed as a single IOC.
        return {"status": "error: no status probe (need SCRIPT_NAME.{pl,sh} or APP_NAME)",
                "host": host, "address": host}

    # Short-circuit on a recent SSH failure to the same host so we
    # don't hammer a rate-limited / down sshd every 5s per IOC.
    cached = _ssh_cached_failure(host)
    if cached is not None:
        return {"status": f"ssh error: {cached} (cached)",
                "host": host, "address": host}

    if use_procserver:
        remote_cmd = (
            f"cd {shlex.quote(work_dir)} && "
            f"./{shlex.quote(script_name)} status 2>&1 "
            f"|| echo __STATUS_FAILED__"
        )
    else:
        # pgrep exits 0 with matching PIDs, 1 with no match. Use -f
        # so we match the full command line — many EPICS ioc apps
        # show as `./tomoScanApp iocBoot/...` etc.
        remote_cmd = (
            f"if pgrep -f {shlex.quote(app_name)} >/dev/null 2>&1; then "
            f"  echo 'is running'; "
            f"else "
            f"  echo 'is not running'; "
            f"fi"
        )
    rc, out, err = _ssh_run(user, host, remote_cmd, timeout=timeout)
    if rc == -1:
        detail = (err.strip() or "ssh failed")
        _ssh_record_failure(host, detail)
        return {"status": f"error: {detail}",
                "host": host, "address": host}
    # rc=255 means ssh itself failed (auth denied, host unreachable,
    # DNS failure). Surface that distinctly so a stale SSH key or a
    # rebooted host doesn't get mis-read as an IOC problem.
    if rc == 255:
        msg = (err or out).strip().splitlines()
        detail = msg[-1] if msg else "ssh failed"
        _ssh_record_failure(host, detail)
        return {"status": f"ssh error: {detail}",
                "host": host, "address": host}

    # SSH succeeded — reset any cached failure for this host.
    _ssh_clear_success(host)
    combined = out + err
    return {
        "status":  _classify_status_output(combined, rc),
        "host":    host,
        "address": host,
    }


def get_status_cgi(ioc: str, timeout: float = 5.0) -> Dict:
    """Legacy status check that scrapes the CGI page listed in
    config. Kept as a fallback for hosts that don't allow SSH from
    this machine. Same return shape as `get_status_direct` (adds an
    `address` field pulled from the CGI-reported IP)."""
    cfg = load_config()
    guis = set(cfg.get("beamline_guis", []))
    if ioc in guis:
        return {"status": "GUI", "host": "N/A", "address": "N/A"}
    try:
        html = requests.get(_cgi_url(cfg), timeout=timeout).text
        match = re.search(r"var\s+iocs\s*=\s*(\[[\s\S]*?\])\s*;", html)
        if not match:
            return {"status": "unavailable", "host": "N/A", "address": "N/A"}
        raw_array = match.group(1)
        json_compatible = _clean_js_array(raw_array)
        ioc_data = json.loads(json_compatible)
        for entry in ioc_data:
            if entry["name"] == ioc:
                address = (".".join(entry["address"])
                           if isinstance(entry["address"], list)
                           else str(entry["address"]))
                return {"status": entry["status"],
                        "host": address, "address": address}
        return {"status": "not found", "host": "N/A", "address": "N/A"}
    except Exception as e:
        return {"status": f"error: {e}", "host": "N/A", "address": "N/A"}


def get_status(ioc: str, timeout: float = 8.0,
               method: str = "direct") -> Dict:
    """Return the current status + host for an IOC.

    `method` selects the source of truth:
      - `"direct"` (default): SSH to the target host parsed from the
        `.sh` script and probe the IOC there. This is the authoritative
        check — matches what the operator would see on the box.
      - `"cgi"`: scrape the CGI status page listed in config
        (`paths.CGI_URL`). Faster but only reflects whatever the CGI
        happens to know about; can lie if the CGI is stale or the
        IOC lives on a host it doesn't poll.
      - `"auto"`: try `direct` first, fall back to `cgi` only when
        the direct probe reports an SSH-layer error.

    Shape: `{"status": <str>, "host": <str>, "address": <str>}`."""
    if method == "cgi":
        return get_status_cgi(ioc, timeout=timeout)
    if method == "direct":
        return get_status_direct(ioc, timeout=timeout)
    if method == "auto":
        st = get_status_direct(ioc, timeout=timeout)
        s = str(st["status"])
        if not (s.startswith("error") or s.startswith("ssh error")):
            return st
        # Only fall back to CGI for IOCs the CGI could plausibly
        # know about — the procServer-registered ones. App-process
        # IOCs (tomoscan family, txmOptics: Python launcher +
        # APP_NAME) are absent from the CGI page, so a CGI fallback
        # would return a bogus "not found" and hide the real SSH
        # error. Return the direct-probe result unchanged for those.
        cfg = load_config()
        flat, _ = _iocs_flat_and_categorized(cfg)
        entry = flat.get(ioc)
        if entry:
            script_path = os.path.join(_scripts_dir(cfg),
                                       f"{entry['script']}.sh")
            if os.path.isfile(script_path):
                meta = _parse_script(script_path)
                sn = meta.get("SCRIPT_NAME") or ""
                if not _is_procserver_style(sn):
                    return st
        return get_status_cgi(ioc, timeout=min(timeout, 5.0))
    raise ValueError(f"unknown status method: {method!r}")


# ── control (start / stop / medm / gui) ─────────────────────────────

def _run_script(ioc: str, action: Optional[str]) -> Dict:
    """Invoke `<scripts_dir>/<script>.sh [action]` for the named
    IOC. Returns `{"ok": True, "script": <path>}` on submit success,
    or `{"error": <msg>}` on failure. `action=None` for GUI launch
    (no argument to the script).

    Sets `IOM_HEADLESS=1` in the subprocess environment so scripts
    sourcing `_lib.sh` know to skip `gnome-terminal` and run
    directly with `nohup` + a log file. This is what lets the CLI
    and the Python API start IOCs from contexts without a working
    desktop session."""
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
    # Force scripts down the headless path — a subprocess launched
    # from an SSH login, systemd, or a Flask worker rarely has a
    # working D-Bus + gnome-terminal combination.
    env.setdefault("IOM_HEADLESS", "1")
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
    "get_status", "get_status_direct", "get_status_cgi",
    "start_ioc", "stop_ioc", "restart_ioc", "medm", "start_gui",
]
