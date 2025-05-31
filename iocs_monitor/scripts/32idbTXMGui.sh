#!/bin/bash

# Define variables
TAB_NAME="TXM GUI"
REMOTE_USER="usertxm"
REMOTE_HOST="txm4"
HOME_DIR="/home/beams/USERTXM"


#!/bin/bash

gnome-terminal --tab --title="TXM GUI" -- bash -c "
    ssh -t $REMOTE_USER@$REMOTE_HOST '
        source ~/.bashrc;
        $HOME_DIR/./start_txm_gui.sh;
        exec bash
    '
"