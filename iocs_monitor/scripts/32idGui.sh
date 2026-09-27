#!/bin/bash
source "$(dirname "$0")/_lib.sh"

# Define variables
TAB_NAME="32ID Gui"
REMOTE_USER="usr32idc"
REMOTE_HOST="txm4"


iom_open "32ID Gui" "
    ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
        ./start_epics
        exec csh
    ';
"
