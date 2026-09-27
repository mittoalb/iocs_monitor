#!/bin/bash
source "$(dirname "$0")/_lib.sh"
ACTION=${1:-start}


# Define variables
TAB_NAME="energy py server"
REMOTE_USER="usertxm"
REMOTE_HOST="txm4"
CONDA_ENV="tomoscan"
SCRIPT_NAME="start_energy.py"
WORK_DIR="/home/beams/USERTXM/epics/synApps/support/energy/iocBoot/iocEnergy_32ID/"

# Open a new tab in gnome-terminal, SSH into tomdet, activate conda, and run Python (without login shell)
iom_open "$TAB_NAME" "
    # ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
        cd ${WORK_DIR}
        conda activate ${CONDA_ENV}
        kill_server.sh ${SCRIPT_NAME}
        python -i ${SCRIPT_NAME}
    # ';
"
