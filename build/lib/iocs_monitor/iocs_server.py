from flask import Flask, render_template
import subprocess
import requests
import re
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
SCRIPTS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "scripts"))

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# --- IOC Configuration (script paths) ---
IOCS = {
    "32IDBSHAKER": "/net/s32dserv/xorApps/epics/synApps_6_3/ioc/32idbShaker/iocBoot/ioc32idbShaker/softioc/32idbShaker.pl",
    "ioc32idaSoft": "/net/s32dserv/xorApps/epics/synApps_6_3/ioc/32idaSoft/iocBoot/ioc32idaSoft/softioc/32idaSoft.pl",
    "ioc32idbSoft": "/net/s32dserv/xorApps/epics/synApps_6_3/ioc/32idbSoft/iocBoot/ioc32idbSoft/softioc/32idbSoft.pl",
    "ioc32idcSoft": "/net/s32dserv/xorApps/epics/synApps_6_3/ioc/32idcSoft/iocBoot/ioc32idcSoft/softioc/32idcSoft.pl"
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

@app.route('/start/<ioc>', methods=['POST'])
def start_ioc(ioc):
    script = IOCS.get(ioc)
    if not script:
        return ("Invalid IOC", 400)
    subprocess.Popen([os.path.join(SCRIPTS_DIR, "start_ioc.sh"), script])
    return ('', 204)

@app.route('/stop/<ioc>', methods=['POST'])
def stop_ioc(ioc):
    script = IOCS.get(ioc)
    if not script:
        return ("Invalid IOC", 400)
    subprocess.Popen([os.path.join(SCRIPTS_DIR, "stop_ioc.sh"), script])
    return ('', 204)

@app.route('/medm/<ioc>', methods=['POST'])
def launch_medm(ioc):
    script = IOCS.get(ioc)
    if not script:
        return ("Invalid IOC", 400)
    subprocess.Popen([os.path.join(SCRIPTS_DIR, "launch_medm.sh"), script])
    return ('', 204)

def main():
    app.run(debug=True, host='0.0.0.0', port=5100)

if __name__ == '__main__':
    main()
