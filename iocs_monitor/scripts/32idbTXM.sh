#!/bin/bash

# --- Configuration ---
REMOTE_USER="usertxm"
REMOTE_HOST="txm4"
IOC_NAME="32idbTXM"
BASE_DIR="/net/s32dserv/xorApps/epics/synApps_6_3/ioc"
WORK_DIR="${BASE_DIR}/32idbTXM/iocBoot/ioc32idbTXM/softioc"
SCRIPT_NAME="32idbTXM.pl"
GNOME_TERMINAL="gnome-terminal"
ACTION=${1:-start}

echo "Launching $IOC_NAME on $REMOTE_HOST with action: $ACTION"

$GNOME_TERMINAL --tab --title="$IOC_NAME" -- bash -c "
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
