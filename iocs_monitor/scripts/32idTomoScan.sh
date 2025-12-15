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

echo "Managing $IOC_NAME on $REMOTE_HOST with action: $ACTION"

if [[ "$ACTION" == "start" ]]; then
    # Start the EPICS IOC in one terminal
    $GNOME_TERMINAL --tab --title="$IOC_NAME IOC" -- bash -c "
    ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
        ~/scripts/kill_IOC.sh ${APP_NAME}
        cd ${WORK_DIR}
        conda activate ${CONDA_ENV}
        ./start_IOC;
    ';
    "

    # Wait a moment for the IOC to start
    sleep 1

    # Start the Python server in another terminal
    $GNOME_TERMINAL --tab --title="$IOC_NAME py server" -- bash -c "
    ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
        bash -l -c \"cd ${WORK_DIR} && hostname &&\
        ~/scripts/kill_server.sh ${SCRIPT_NAME} && \
        source ${CONDA_PATH}/etc/profile.d/conda.sh && \
        conda activate ${CONDA_ENV} && \
        python -i ${SCRIPT_NAME}; \"
    '
    "

elif [[ "$ACTION" == "stop" ]]; then
    # Stop both the IOC and Python server
    $GNOME_TERMINAL --tab --title="$IOC_NAME - Stop" -- bash -c "
    ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
        echo \"Stopping tomoScan IOC and Python server...\"
        ~/scripts/kill_IOC.sh ${APP_NAME}
        ~/scripts/kill_server.sh ${SCRIPT_NAME}
        echo \"Done.\"
        exec bash
    ';
    "

else
    echo "Unknown action: $ACTION"
    echo "Usage: $0 {start|stop|medm}"
    exit 1
fi
