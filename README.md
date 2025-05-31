# IOC Control Panel

A simple web-based control panel to manage EPICS IOCs and GUIs via SSH scripts. The application allows you to start, stop, and launch MEDM for selected IOCs and Beamline GUIs, as well as view live status where applicable.

## Features

- Start, stop, and launch MEDM interfaces for IOCs
- Group support for Beamline GUIs vs other IOCs
- Periodic live status refresh using CGI page scraping
- Optional dark mode toggle
- Configurable via a single `config.json` file

## Requirements

- Python 3.6+
- Flask
- curl or wget for CGI status page (accessed via requests)

## Installation

1. Clone this repository or copy the files to your target host:

```bash
git clone https://your-git-repo/ioc-control-panel.git
cd ioc-control-panel
```

2. Install Python dependencies:

```bash
pip install flask requests
```

3. Configure the application:

Edit the `config.json` file:

```json
{
  "paths": {
    "template_dir": "templates",
    "scripts_dir": "/absolute/path/to/ioc/scripts",
    "CGI_URL": "http://yourhost/cgi-bin/ioc_alive.cgi"
  },
  "iocs": {
    "iocExample1": "script1",
    "iocTXM": "32TXM"
  },
  "excluded": [
    "iocExample1"
  ],
  "beamline_guis": ["iocTXM"]
}
```

- `iocs` maps IOC names to script names (used to run `script_name.sh start|stop|medm`)
- `excluded` lists IOCs that should not have control buttons
- `beamline_guis` lists IOCs to group in a separate section (e.g., TXM GUIs)

## Usage

Start the server with:

```bash
python iocs_server.py
```

Then open a browser and go to:

```
http://localhost:5100
```

## File Structure

```
iocs_monitor/
├── iocs_server.py       # Main Flask server
├── config.json          # Configuration for IOC names and paths
├── templates/
│   └── index.html       # Web UI layout and JS
├── scripts/
│   └── *.sh             # IOC control scripts (must support start/stop/medm)
```

## Script Requirements

Each IOC script must accept one of the following as its first argument:

```bash
./your_script.sh start
./your_script.sh stop
./your_script.sh medm
```

The server will call these via `subprocess.Popen`.

## Notes

- Beamline GUI entries (e.g., `iocTXM`) are not checked for status via the CGI — they return "GUI" or "N/A" as status.
- The IOC status is parsed from a CGI page that must return a `var iocs = [...]` JavaScript variable.

## License


