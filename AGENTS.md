# iocs_monitor — agent documentation

Two ways for an AI agent to drive this package:

1. **`iom-cli`** — argparse CLI, one subcommand per operation.
   Same actions as the Flask REST endpoints, callable from `bash`.
2. **`from iocs_monitor import headless as h`** — pure-Python API,
   no Flask, no HTTP, no server.

The web server (`iom`, Flask on port 5100) shares the same
config, scripts, and probe/launch logic — its `/status/<ioc>`
route delegates to `headless.get_status(method="auto")` (direct
SSH with CGI fallback), and its start/stop/medm/gui handlers pass
`IOM_HEADLESS=1` to `Popen`, matching what the CLI does.

## What iocs_monitor is

Web + CLI control panel for EPICS IOCs at APS 32-ID. Config-driven
(`iocs_monitor/config.json` — categorized IOCs, each mapped to a
`.sh` script under `iocs_monitor/scripts/`). Every IOC operation is
`subprocess.Popen([script, action])` where `action` ∈
{`start`, `stop`, `medm`} or absent for GUI launch.

**Status**: probed directly on the target host by default — the
Python API SSHes to the `REMOTE_HOST` parsed from each script and
runs whichever probe fits the script's shape:

- **procServer-style** (`SCRIPT_NAME` ends in `.pl` / `.sh` — e.g.
  `32idbTXM.pl`): `cd $WORK_DIR && ./$SCRIPT_NAME status`, look for
  `is running`.
- **App-process style** (`SCRIPT_NAME` is a Python file + `APP_NAME`
  is defined — e.g. `start_tomoscan.py` + `tomoScanApp`):
  `pgrep -f $APP_NAME` on the remote.

Fall back to `--method cgi` (or `method="cgi"`) for the legacy
CGI-scrape behavior, or `auto` to try SSH first and only scrape the
CGI when SSH fails. Compound / GUI-wrapper scripts (e.g.
`32idbTXM_full.sh`) fit neither probe and always return an error
under `direct`; use `cgi` for those.

**Terminal**: control scripts source `scripts/_lib.sh` and use its
`iom_open` helper, which drops into a headless `nohup + logfile`
mode when `gnome-terminal` is missing, has no DISPLAY, or no D-Bus
session. The Python API always sets `IOM_HEADLESS=1` before
`Popen`, so `iom-cli` and REST-triggered starts no longer depend
on a working desktop session. Logs land in
`$IOM_LOGDIR` (default `$HOME/.iocs_monitor/logs`).

## `iom-cli` — one-shot operations

```bash
# Discovery
iom-cli list                            # every IOC + category + script
iom-cli list --category TXM             # filter to one category
iom-cli list --json                     # machine-readable
iom-cli categories                      # every category name

# Status (SSHes to the target host by default)
iom-cli status ioc32idbTXM                     # procServer-style probe
iom-cli status ioc32idTomoScanStep             # pgrep-on-APP_NAME probe
iom-cli status ioc32idbSP1 --method cgi        # legacy CGI scrape
iom-cli status ioc32idbSP1 --method auto       # SSH, fall back to CGI
iom-cli --json status ioc32idbSP1

# Control (fires the .sh script in a detached subprocess)
iom-cli start   ioc32idbTXM
iom-cli stop    ioc32idbTXM
iom-cli restart ioc32idbTXM             # stop then start
iom-cli medm    ioc32idbTXM             # open the MEDM display
iom-cli gui     TXMbackend              # launch a GUI-style entry (no arg)
```

Every subcommand accepts `--json` where a read makes sense.
Nonzero exit on failure.

## Python API

```python
from iocs_monitor import headless as h

# Discovery
h.list_iocs()                           # flat list, all
h.list_iocs(category="TXM")             # filter
h.list_categories()                     # every category

# Status
h.get_status("ioc32idbTXM")                     # direct SSH probe
h.get_status("ioc32idbTXM", method="cgi")       # legacy CGI scrape
h.get_status("ioc32idbTXM", method="auto")      # SSH, fall back to CGI
h.get_status_direct("ioc32idbTXM")              # explicit
h.get_status_cgi("ioc32idbTXM")                 # explicit

# Control
h.start_ioc("ioc32idbTXM")              # {"ok": True, "script": ...}
h.stop_ioc("ioc32idbTXM")
h.restart_ioc("ioc32idbTXM")
h.medm("ioc32idbTXM")
h.start_gui("TXMbackend")
```

Every function returns a dict; control functions return either
`{"ok": True, "script": <path>, "action": <name>}` on submit or
`{"error": <message>}` on failure. `Popen` is fire-and-forget —
"submitted" means the shell script started, not that the IOC is up.
Follow with `get_status` after a settle delay if you need to confirm.

## Data shapes

### `list_iocs()` returns

```python
[
  {
    "name":        "ioc32idbTXM",
    "script":      "32idbTXM",
    "description": "Main TXM control IOC",
    "category":    "TXM",
    "is_gui":      False,
  },
  ...
]
```

### `get_status()` returns

Every return shape now carries `host` (the target machine parsed
from the script) and `address` (kept as an alias for
backwards-compat with CGI callers). Common values:

```python
# --- direct (default) ---
{"status": "up",              "host": "txm4",    "address": "txm4"}
{"status": "down",            "host": "txm4",    "address": "txm4"}
{"status": "GUI",             "host": "N/A",     "address": "N/A"}
{"status": "unknown",         "host": "txm4",    "address": "txm4"}
{"status": "ssh error: ...",  "host": "txm4",    "address": "txm4"}
{"status": "error: script missing vars: ...", "host": "...", "address": "..."}

# --- cgi ---
{"status": "up",              "host": "10.54.102.11", "address": "10.54.102.11"}
{"status": "unavailable",     "host": "N/A",     "address": "N/A"}
{"status": "not found",       "host": "N/A",     "address": "N/A"}
{"status": "error: ...",      "host": "N/A",     "address": "N/A"}
```

## When to use `iom-cli` vs. the REST API

- **`iom-cli` / Python API** — from an agent or script. No web server
  needed (though `iom` can be running; the two don't conflict). Fast,
  local, direct.
- **REST API** (`iom` running, HTTP to `http://<host>:5100/…`) — from
  the browser UI, or from external tools that already speak HTTP.

Both share the same `.sh` scripts and the same config, so behavior
matches whichever you use.

## When NOT to use this

- **Don't SSH directly to the IOC hosts.** The `.sh` scripts encode
  screen-session naming, environment setup, and start-order the
  IOCs expect. Manual ssh + start bypasses that.
- **Don't invoke the `.sh` scripts from a shell terminal directly.**
  Some spawn `gnome-terminal` windows the user doesn't want in their
  workflow. `iom-cli` / the Python API use `Popen(..., start_new_session=True)`
  with a controlled environment.
- **Don't hand-edit `config.json` casually.** The scripts and the
  config must match — script names in `config.json` must exist as
  `.sh` files under the `scripts_dir`.

## Config

`iocs_monitor/config.json` is the single source of truth. Keys:

- `paths.scripts_dir` — absolute path to the `.sh` scripts.
- `paths.CGI_URL` — CGI page URL that `get_status` scrapes.
- `paths.template_dir` — Flask templates (server-only).
- `excluded` — VME crate IOCs shown but not controllable.
- `beamline_guis` — names of GUI-style entries (no start/stop action,
  just script invocation).
- Any other top-level dict → a category; its keys are IOC names.
  Each IOC value is a `{"script", "description"}` dict (or a bare
  script name string, legacy format — auto-normalized).

## Install

```bash
pip install -e /home/beams/AMITTONE/Software/iocs_monitor
```

Installs both `iom` (Flask server) and `iom-cli` console scripts.
The AI agent picks up `iocs_monitor` automatically when it's listed
in `~/.pystream/agent_packages.json` (see beamline-agent's discovery
convention — `AGENTS.md` at repo root → agent reads it as
`~/.pystream/docs/iocs_monitor_AGENTS.md`).

## Common gotchas

- **`DISPLAY` unset** → `_run_script` defaults to `:1`, and `IOM_HEADLESS=1`
  is always set so scripts skip `gnome-terminal` and log to
  `$IOM_LOGDIR` (default `$HOME/.iocs_monitor/logs`). If a script
  launches an X GUI in a session with a different display, override
  `DISPLAY` in the calling shell.
- **SSH auth denied** → direct status returns `ssh error: ...`.
  Passwordless SSH from the account running `iocs_monitor` to the
  target host must be set up (same requirement the `.sh` scripts
  have always had). Test with
  `ssh -o BatchMode=yes usertxm@<host> true`.
- **CGI page unreachable** → `get_status(..., method="cgi")` returns
  `error: ...`. Not a bug; just a network issue. Fall back to `caget`
  on a known PV.
- **Script metadata unparseable** → for the direct probe, the script
  must define `REMOTE_USER`, `REMOTE_HOST`, and either
  (`WORK_DIR` + `SCRIPT_NAME` ending in `.pl`/`.sh`) for the
  procServer-style probe, or `APP_NAME` for the pgrep-style probe.
  All values must be top-level `VAR="value"` assignments (a
  one-pass `${VAR}` expansion against earlier lines is done, so
  `WORK_DIR="${BASE_DIR}/foo"` is fine). Compound scripts (e.g.
  `32idbTXM_full.sh`) don't fit either shape and always return an
  error under `method="direct"`; use `method="cgi"` for those.
- **Script not found** → the config lists an IOC whose `.sh` file is
  missing under `scripts_dir`. Fix by editing `config.json` or
  dropping the `.sh` in place.
- **`Popen` returns immediately** — success only means the process
  started, not that the IOC is running. Wait a few seconds then call
  `get_status`.

## Files touched by an agent

- Read-only: `config.json`, any `.sh` in `scripts_dir`.
- Fire-and-forget: `subprocess.Popen` on `.sh` scripts.
- No filesystem writes from `iocs_monitor` itself.
