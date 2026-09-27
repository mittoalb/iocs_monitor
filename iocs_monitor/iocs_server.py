from flask import Flask, render_template
import subprocess
import requests
import re
import json
import os

from . import headless

def load_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    with open(config_path) as f:
        return json.load(f), script_dir

# Load config
config, BASE_DIR = load_config()
TEMPLATE_DIR = os.path.join(BASE_DIR, config["paths"]["template_dir"])
SCRIPTS_DIR = config["paths"]["scripts_dir"]
CGI_URL = config["paths"]["CGI_URL"]

# Create a flat dictionary for lookups and a categorized one for display
IOCS_FLAT = {}
IOCS_CATEGORIZED = {}

for key, value in config.items():
    if key not in ["paths", "excluded", "beamline_guis"]:
        if isinstance(value, dict):
            # Handle both old format (string) and new format (dict with script/description)
            normalized_iocs = {}
            for ioc_name, ioc_data in value.items():
                if isinstance(ioc_data, str):
                    # Old format: just a script name
                    IOCS_FLAT[ioc_name] = {"script": ioc_data, "description": ""}
                    normalized_iocs[ioc_name] = {"script": ioc_data, "description": ""}
                else:
                    # New format: dict with script and description
                    IOCS_FLAT[ioc_name] = ioc_data
                    normalized_iocs[ioc_name] = ioc_data
            
            IOCS_CATEGORIZED[key] = normalized_iocs

VME_IOCS = set(config.get("excluded", []))
BEAMLINE_GUI_NAMES = set(config.get("beamline_guis", []))

app = Flask(__name__, template_folder=TEMPLATE_DIR)

@app.route('/')
def index():
    # Separate beamline GUIs and categorize other IOCs
    beamline_guis = {k: v for k, v in IOCS_FLAT.items() if k in BEAMLINE_GUI_NAMES}
    
    # Create categorized IOCs without the GUI ones
    categorized_iocs = {}
    for category, iocs in IOCS_CATEGORIZED.items():
        categorized_iocs[category] = {k: v for k, v in iocs.items() if k not in BEAMLINE_GUI_NAMES}
    
    return render_template(
        'index.html',
        categorized_iocs=categorized_iocs,
        beamline_guis=beamline_guis,
        excluded_iocs=VME_IOCS
    )

def clean_js_array(js_array_str):
    js_array_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js_array_str)
    js_array_str = re.sub(r",\s*([}\]])", r"\1", js_array_str)
    return js_array_str

@app.route('/status/<ioc>', methods=['POST'])
def check_status(ioc):
    # Delegate to the headless probe in `auto` mode:
    #   - Try direct SSH first (works for both procServer-style
    #     IOCs and app-process IOCs like tomoscan via pgrep on
    #     APP_NAME).
    #   - If SSH fails AND the IOC is procServer-style, fall back to
    #     the CGI scrape (which lists those).
    #   - If SSH fails AND the IOC is app-process style (tomoscan,
    #     txmOptics), keep the SSH error — the CGI has no record of
    #     those and would return a misleading "not found".
    st = headless.get_status(ioc, method="auto", timeout=6.0)
    # Keep the response shape the frontend expects: {status, address}
    return {"status": st.get("status", "unknown"),
            "address": st.get("address") or st.get("host") or "N/A"}

def run_script_for_ioc(ioc, action):
    ioc_data = IOCS_FLAT.get(ioc)
    if not ioc_data:
        return ({"error": "Invalid IOC"}, 400)

    script_name = ioc_data.get("script") if isinstance(ioc_data, dict) else ioc_data
    script_path = os.path.join(SCRIPTS_DIR, f"{script_name}.sh")
    print("Executing", script_path)
    if not os.path.isfile(script_path):
        return ({"error": f"Script not found: {script_path}"}, 404)
    try:
        env = os.environ.copy()
        if 'DISPLAY' not in env:
            env['DISPLAY'] = ':1'
        env.setdefault('IOM_HEADLESS', '1')
        subprocess.Popen([script_path, action], env=env, start_new_session=True)
        return ({"status": "success", "message": f"{action} command sent"}, 200)
    except Exception as e:
        return ({"error": f"Failed to run script: {str(e)}"}, 500)

@app.route('/gui/<ioc>', methods=['POST'])
def start_gui(ioc):
    ioc_data = IOCS_FLAT.get(ioc)
    if not ioc_data:
        return ({"error": "Invalid GUI IOC"}, 400)

    script_name = ioc_data.get("script") if isinstance(ioc_data, dict) else ioc_data
    script_path = os.path.join(SCRIPTS_DIR, f"{script_name}.sh")
    if not os.path.isfile(script_path):
        return ({"error": f"Script not found: {script_path}"}, 404)
    try:
        env = os.environ.copy()
        if 'DISPLAY' not in env:
            env['DISPLAY'] = ':1'
        env.setdefault('IOM_HEADLESS', '1')
        subprocess.Popen([script_path], env=env, start_new_session=True)
        return ({"status": "success", "message": "GUI started"}, 200)
    except Exception as e:
        return ({"error": f"Failed to run GUI script: {str(e)}"}, 500)

@app.route('/start/<ioc>', methods=['POST'])
def start_ioc(ioc):
    return run_script_for_ioc(ioc, "start")

@app.route('/stop/<ioc>', methods=['POST'])
def stop_ioc(ioc):
    return run_script_for_ioc(ioc, "stop")

@app.route('/medm/<ioc>', methods=['POST'])
def launch_medm(ioc):
    return run_script_for_ioc(ioc, "medm")

def main():
    app.run(debug=True, host='0.0.0.0', port=5100)

if __name__ == '__main__':
    main()
