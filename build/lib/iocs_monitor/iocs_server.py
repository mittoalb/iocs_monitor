from flask import Flask, render_template
import subprocess
import requests
import re
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
#SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
SCRIPTS_DIR = "~/Software/sandbox/epics/iocs_monitor/iocs_monitor/scripts/"

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# --- IOC Configuration (script name identifiers) ---
IOCS = {
    "32IDBSHAKER": "32idbShaker",
    "ioc32idaSoft": "32idaSoft",
    "ioc32idbSoft": "32idbSoft",
    "ioc32idcSoft": "32idcSoft"
}

CGI_URL = "https://7id.xray.aps.anl.gov/cgi-bin/ioc_alive.cgi"

@app.route('/')
def index():
    return render_template('index.html', iocs=IOCS)

def clean_js_array(js_array_str):
    js_array_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js_array_str)
    js_array_str = re.sub(r",\s*([}\]])", r"\1", js_array_str)
    return js_array_str

@app.route('/status/<ioc>', methods=['POST'])
def check_status(ioc):
    try:
        html = requests.get(CGI_URL, timeout=5).text
        match = re.search(r"var\s+iocs\s*=\s*(\[[\s\S]*?\])\s*;", html)
        if not match:
            return {"status": "unavailable", "address": "N/A"}

        raw_array = match.group(1)
        json_compatible = clean_js_array(raw_array)
        ioc_data = json.loads(json_compatible)

        for entry in ioc_data:
            if entry["name"] == ioc:
                address = ".".join(entry['address']) if isinstance(entry['address'], list) else str(entry['address'])
                return {
                    "status": entry["status"],
                    "address": address
                }

        return {"status": "not found", "address": "N/A"}

    except Exception as e:
        return {"status": f"error: {e}", "address": "N/A"}

def run_script_for_ioc(ioc, action):
    name = IOCS.get(ioc)
    if not name:
        return ("Invalid IOC", 400)

    script_path = os.path.join(SCRIPTS_DIR, f"{name}.sh")
    print(script_path)
    if not os.path.isfile(script_path):
        return (f"Script not found: {script_path}", 404)

    try:
        subprocess.Popen([script_path, action])
        return ('', 204)
    except Exception as e:
        return (f"Failed to run script: {str(e)}", 500)

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
