#!/bin/bash

# Define variables
TAB_NAME="32ID Gui"
REMOTE_USER="usr32idc"
REMOTE_HOST="txm4"


gnome-terminal --tab --title "32ID Gui" -- bash -c "
    ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
        ./start_epics
        exec csh
    ';
"
