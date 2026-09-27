#!/bin/bash
source "$(dirname "$0")/_lib.sh"

# --- Configuration ---
REMOTE_USER="usertxm"
REMOTE_HOST="gauss"
IOC_NAME="tomoScanFly"
CONDA_ENV="tomoscan"
APP_NAME="tomoScanApp"
WORK_DIR="/home/beams/USERTXM/epics/synApps/support/tomoscan/iocBoot/iocTomoScan_32ID_FLY/"
SCRIPT_NAME="start_tomoscan.py"
CONDA_PATH="/home/beams/USERTXM/conda/anaconda/"
GNOME_TERMINAL="gnome-terminal"
ACTION=${1:-start}

# Ensure DISPLAY is set for GUI applications
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:1
fi

echo "Managing $IOC_NAME on $REMOTE_HOST with action: $ACTION"

if [[ "$ACTION" == "start" ]]; then
    # Start IOC in first terminal
    iom_open "$IOC_NAME IOC" "
ssh -Y ${REMOTE_USER}@${REMOTE_HOST} bash << EOF
~/scripts/kill_IOC.sh ${APP_NAME}
cd ${WORK_DIR}
source ${CONDA_PATH}/etc/profile.d/conda.sh
conda activate ${CONDA_ENV}
./start_IOC
exec bash
EOF
    " &

    # Wait a moment then start Python server in second terminal
    sleep 1
    iom_open "$IOC_NAME py server" "
ssh -Y ${REMOTE_USER}@${REMOTE_HOST} bash << EOF
cd ${WORK_DIR}
~/scripts/kill_server.sh ${SCRIPT_NAME}
source ${CONDA_PATH}/etc/profile.d/conda.sh
conda activate ${CONDA_ENV}
python -i ${SCRIPT_NAME}
exec bash
EOF
    " &

elif [[ "$ACTION" == "stop" ]]; then
    # Stop both the IOC and Python server
    iom_open "$IOC_NAME - Stop" "
ssh -Y ${REMOTE_USER}@${REMOTE_HOST} bash << EOF
echo \"Stopping ${IOC_NAME} IOC and Python server...\"
~/scripts/kill_IOC.sh ${APP_NAME}
~/scripts/kill_server.sh ${SCRIPT_NAME}
echo \"Done.\"
exec bash
EOF
    " &

else
    echo "Unknown action: $ACTION"
    echo "Usage: $0 {start|stop|medm}"
    exit 1
fi
