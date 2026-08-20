# iocs_monitor — agent documentation

Two ways for an AI agent to drive this package:

1. **`iom-cli`** — argparse CLI, one subcommand per operation.
   Same actions as the Flask REST endpoints, callable from `bash`.
2. **`from iocs_monitor import headless as h`** — pure-Python API,
   no Flask, no HTTP, no server.

The web server (`iom`, Flask on port 5100) is unchanged and still
serves the browser UI — the two entry points are additive.

## What iocs_monitor is

Web + CLI control panel for EPICS IOCs at APS 32-ID. Config-driven
(`iocs_monitor/config.json` — categorized IOCs, each mapped to a
`.sh` script under `iocs_monitor/scripts/`). Every IOC operation is
`subprocess.Popen([script, action])` where `action` ∈
{`start`, `stop`, `medm`} or absent for GUI launch. Status is scraped
from a CGI page listed in `config.json`.

## `iom-cli` — one-shot operations

```bash
# Discovery
iom-cli list                            # every IOC + category + script
iom-cli list --category TXM             # filter to one category
iom-cli list --json                     # machine-readable
iom-cli categories                      # every category name

# Status (scrapes the CGI page from config)
iom-cli status ioc32idbTXM
iom-cli status ioc32idbSP1 --json

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
h.get_status("ioc32idbTXM")             # {"status": ..., "address": ...}

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

```python
{"status": "up",         "address": "164.54.102.6"}   # normal
{"status": "down",       "address": "N/A"}             # CGI says down
{"status": "GUI",        "address": "N/A"}             # is_gui entry
{"status": "unavailable","address": "N/A"}             # CGI didn't parse
{"status": "not found",  "address": "N/A"}             # IOC absent from CGI
{"status": "error: ...", "address": "N/A"}             # network failure
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

- **`DISPLAY` unset** → `_run_script` defaults to `:1`. If a script
  launches a Qt/GTK GUI in a session with a different display, override
  the env var in the calling shell.
- **CGI page unreachable** → `get_status` returns `error: ...`. Not
  a bug; just a network issue. Fall back to `caget` on a known PV
  the IOC serves.
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
