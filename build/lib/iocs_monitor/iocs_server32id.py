from flask import Flask, render_template
import subprocess
import requests
import re
import json
import os

# Create ssh and copy to target machine
# Example:
# ssh-keygen -t rsa -b 4096 -C "merlot"
# ssh-copy-id -i ~/.ssh/id_rsa_txm4.pub usertxm@txm4


# Load config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.json")) as f:
    config = json.load(f)

# Extract paths
TEMPLATE_DIR = os.path.join(BASE_DIR, config["paths"]["template_dir"])
SCRIPTS_DIR = config["paths"]["scripts_dir"]
CGI_URL = config["paths"]["CGI_URL"]

# Extract IOC settings
IOCS = config["iocs"]
VME_IOCS = set(config.get("excluded", []))


app = Flask(__name__, template_folder=TEMPLATE_DIR)


@app.route('/')
def index():
    return render_template('index.html', iocs=IOCS, excluded_iocs=VME_IOCS)

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
        print('here')
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
