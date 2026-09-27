#!/bin/bash
source "$(dirname "$0")/_lib.sh"

# Define variables
TAB_NAME="TXM GUI"
REMOTE_USER="usertxm"
REMOTE_HOST="txm4"
HOME_DIR="/home/beams/USERTXM"

#!/bin/bash

iom_open "TXM GUI" "
    ssh -X $REMOTE_USER@$REMOTE_HOST '
        source ~/.bashrc;
        $HOME_DIR/./start_txm_gui.sh;
        exec bash
    '
"

