#!/bin/bash
source "$(dirname "$0")/_lib.sh"

# --- Configuration ---
REMOTE_USER="usertxm"
REMOTE_HOST="txm4"
IOC_NAME="32IDcSoft"
BASE_DIR="/net/s32dserv/xorApps/epics/synApps_6_3/ioc"
WORK_DIR="${BASE_DIR}/32idcSoft/iocBoot/ioc32idcSoft/softioc"
SCRIPT_NAME="32idcSoft.pl"
GNOME_TERMINAL="gnome-terminal"
ACTION=${1:-start}

echo "Launching $IOC_NAME on $REMOTE_HOST with action: $ACTION"

iom_open "$IOC_NAME" "
ssh -Y ${REMOTE_USER}@${REMOTE_HOST} bash << 'EOF'
source ~/.bashrc
cd \"${WORK_DIR}\" || exit 1

STATUS=\$(./${SCRIPT_NAME} status 2>&1 || echo \"__STATUS_FAILED__\")

if [[ \"${ACTION}\" == \"start\" || \"${ACTION}\" == \"stop\" ]]; then
    if echo \"\$STATUS\" | grep -q \"is running\"; then
        echo \"$IOC_NAME is running. Stopping it...\"
        ./${SCRIPT_NAME} stop
        sleep 2
    else
        echo \"$IOC_NAME is not running.\"
    fi
fi

if [[ \"${ACTION}\" != \"stop\" ]]; then
    echo \"Running action: ${ACTION}\"
    ./${SCRIPT_NAME} ${ACTION}
fi

exec bash
EOF
"
