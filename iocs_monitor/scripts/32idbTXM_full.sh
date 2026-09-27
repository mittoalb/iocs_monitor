#!/bin/bash
source "$(dirname "$0")/_lib.sh"
ACTION=${1:-start}


# Define variables
TAB_NAME="TXM server"
REMOTE_USER="usertxm"
REMOTE_HOST="txm4"
CONDA_ENV="tomoscan"
WORK_DIR="/home/beams/USERTXM/epics/synApps/support/"
HOME_DIR="/home/beams/USERTXM"

if [[ \"${ACTION}\" == \"stop\" ]]; then

    iom_open "txmOptics IOC" "
        ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            cd $WORK_DIR/txmoptics/iocBoot/iocTXMOptics/; \
            pkill -9 txmOpticsApp; \
            ./start_IOC;\
            bash
        ';
    "
    iom_open "tomoScan IOC" "
        ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            cd $WORK_DIR/tomoscan/iocBoot/iocTomoScan_32ID/; \
            pkill -9 tomoScanApp; \
            bash
        ';
    "
fi
 
if [[ \"${ACTION}\" == \"start\" ]]; then

    #TXM optics server
    echo "Starting TXM control"
    iom_open "txmOptics py server" "
        ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
            $HOME_DIR/./start_txm.sh'
            bash
        ';
    "
    #xterm -title "tomoScan step IOC"  -e bash -l -c "\
    #cd $WORK_DIR/tomoscan/iocBoot/iocTomoScan_32ID_STEP/; \
    #./start_IOC;\
    #bash" 

    #xterm -title "tomoScanStep py server"  -e bash -l -c "\
    #cd $WORK_DIR/tomoscan/iocBoot/iocTomoScan_32ID_STEP/; \
    #source ~/.bashrc; python -i start_tomoscan.py;\
    #bash"
fi

if [[ \"${ACTION}\" == \"medm\" ]]; then

    echo "Starting TXM GUI"
    iom_open "TXM GUI" "
        # ssh -Y ${REMOTE_USER}@${REMOTE_HOST} '
            $HOME_DIR/./start_txm_gui.sh 
            bash
        # ';
    "
fi
