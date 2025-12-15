#!/bin/bash

# --- Configuration ---
REMOTE_USER="usertxm"
REMOTE_HOST="gauss"
IOC_NAME="tomoScan"
CONDA_ENV="tomoscan"
APP_NAME="tomoScanApp"
WORK_DIR="/home/beams/USERTXM/epics/synApps/support/tomoscan/iocBoot/iocTomoScan_32ID/"
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
    # Launch a single gnome-terminal with two tabs
    $GNOME_TERMINAL \
        --tab --title="$IOC_NAME IOC" -- bash -c "
            ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
                ~/scripts/kill_IOC.sh ${APP_NAME}
                cd ${WORK_DIR}
                source ${CONDA_PATH}/etc/profile.d/conda.sh
                conda activate ${CONDA_ENV}
                ./start_IOC
                exec bash
            '
        " \
        --tab --title="$IOC_NAME py server" -- bash -c "
            sleep 2
            ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
                cd ${WORK_DIR}
                ~/scripts/kill_server.sh ${SCRIPT_NAME}
                source ${CONDA_PATH}/etc/profile.d/conda.sh
                conda activate ${CONDA_ENV}
                python -i ${SCRIPT_NAME}
                exec bash
            '
        "

elif [[ "$ACTION" == "stop" ]]; then
    # Stop both the IOC and Python server
    $GNOME_TERMINAL --tab --title="$IOC_NAME - Stop" -- bash -c "
        ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
            echo \"Stopping tomoScan IOC and Python server...\"
            ~/scripts/kill_IOC.sh ${APP_NAME}
            ~/scripts/kill_server.sh ${SCRIPT_NAME}
            echo \"Done.\"
            exec bash
        '
    "

else
    echo "Unknown action: $ACTION"
    echo "Usage: $0 {start|stop|medm}"
    exit 1
fi
