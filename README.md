# IOC Control Panel

A web-based control panel to manage EPICS IOCs and GUIs via SSH scripts. The application allows you to start, stop, and launch MEDM for selected IOCs and Beamline GUIs, with organized categorical views and live status monitoring.

## Features

- **IOC Management**: Start, stop, and launch MEDM interfaces for IOCs
- **Categorical Organization**: Group IOCs by category (e.g., TXM, Projection Microscope, etc.)
- **Beamline GUIs**: Separate section for GUI-only applications
- **IOC Descriptions**: Add descriptions to each IOC for better documentation
- **Live Status Monitoring**: Periodic automatic status refresh using CGI page scraping
- **Dark Mode**: Toggle between light and dark themes with persistent preference
- **Flexible Configuration**: Single `config.json` file for all settings

## Requirements

- Python 3.6+
- Flask
- requests

## Installation

1. Clone this repository:
```bash
git clone https://github.com/mittoalb/iocs_monitor.git
cd iocs_monitor
```

2. Install Python dependencies:
```bash
pip install flask requests
```

3. Configure the application by editing `config.json` (see Configuration section below)

## Configuration

Edit the `config.json` file to match your setup:

```json
{
  "paths": {
    "template_dir": "templates",
    "scripts_dir": "/absolute/path/to/ioc/scripts",
    "CGI_URL": "https://yourbeamline.xray.aps.anl.gov/cgi-bin/ioc_alive.cgi"
  },
  "iocs": {
    "ioc32idaSoft": {
      "script": "32idaSoft",
      "description": "32-ID-A Soft IOC for general control"
    },
    "ioc32idbSoft": {
      "script": "32idbSoft",
      "description": "32-ID-B Soft IOC for general control"
    }
  },
  "TXM": {
    "ioc32idbTXM": {
      "script": "32idbTXM",
      "description": "Main TXM control IOC"
    },
    "TXM": {
      "script": "32idbTXMGui",
      "description": "TXM graphical user interface"
    }
  },
  "Projection Microscope": {
    "ioc32Kinetix": {
      "script": "32idKinetix",
      "description": "Kinetix camera control"
    }
  },
  "excluded": [
    "ioc32ida",
    "ioc32idb"
  ],
  "beamline_guis": ["TXM", "32ID-GUI"]
}
```

### Configuration Options

- **paths**: 
  - `template_dir`: Directory containing HTML templates (default: "templates")
  - `scripts_dir`: Absolute path to IOC control scripts
  - `CGI_URL`: URL to the IOC status CGI page

- **IOC Categories**: Any top-level key (except `paths`, `excluded`, `beamline_guis`) becomes a category
  - Each IOC entry contains:
    - `script`: The script filename (without .sh extension)
    - `description`: Optional description displayed in the UI

- **excluded**: List of IOC names that should not have control buttons (e.g., VME crate IOCs)

- **beamline_guis**: List of IOC names to display in the "Beamline GUIs" section

## Usage

1. Start the server:
```bash
python iocs_server.py
```

2. Open your browser and navigate to:
```
http://localhost:5100
```

3. Use the interface to:
   - **Start/Stop IOCs**: Click the respective buttons
   - **Launch MEDM**: Click the MEDM button for any IOC
   - **Start GUIs**: Click Start for Beamline GUI applications
   - **Toggle Dark Mode**: Click the 🌙/☀️ button in the top-right corner
   - **Monitor Status**: Status updates automatically every 5 seconds

## File Structure

```
iocs_monitor/
├── iocs_server.py       # Main Flask server
├── config.json          # Configuration for IOC names, categories, and paths
├── templates/
│   └── index.html       # Web UI layout with JavaScript
└── scripts/
    └── *.sh             # IOC control scripts (must support start/stop/medm)
```

## Script Requirements

Each IOC script must be executable and accept one of the following arguments:

```bash
./your_script.sh start   # Start the IOC
./your_script.sh stop    # Stop the IOC
./your_script.sh medm    # Launch MEDM interface
```

For GUI scripts, no arguments are required:
```bash
./your_gui_script.sh     # Launch the GUI application
```

The server executes these scripts via `subprocess.Popen()`.

## Status Monitoring

- **Regular IOCs**: Status is retrieved from the CGI page that returns a JavaScript variable `var iocs = [...]`
- **Beamline GUIs**: Display static "GUI" status and "N/A" address
- **Excluded IOCs**: Show "VME Crates IOCs" instead of control buttons
- **Auto-refresh**: Status updates every 5 seconds automatically

## Dark Mode

The application includes a dark mode toggle that:
- Switches between light and dark color schemes
- Saves preference to browser localStorage
- Persists across page refreshes

## Notes

- The CGI status page must return IOC data in the format: `var iocs = [{name: "...", status: "...", address: [...]}];`
- Beamline GUI entries do not query the CGI for status
- VME crate IOCs (listed in `excluded`) display informational text instead of control buttons
- All IOCs are organized by category for better management of large beamline setups

## Troubleshooting

**"Script not found" error:**
- Verify the `scripts_dir` path in `config.json` is correct
- Ensure script files exist with `.sh` extension
- Check that scripts have execute permissions: `chmod +x script.sh`

**Status shows "error" or "unavailable":**
- Verify the `CGI_URL` is accessible from the server
- Check that the CGI returns the expected JavaScript format
- Review server console for detailed error messages

**Git push authentication errors:**
- Use HTTPS: `git remote set-url origin https://github.com/mittoalb/iocs_monitor.git`
- Or set up SSH keys for GitHub authentication

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
