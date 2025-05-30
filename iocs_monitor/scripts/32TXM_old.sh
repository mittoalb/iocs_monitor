#!/bin/bash
ACTION=${1:-start}


# Define variables
TAB_NAME="TXM server"
REMOTE_USER="usertxm"
REMOTE_HOST="txm4"
CONDA_ENV="tomoscan"
WORK_DIR="/home/beams/USERTXM/epics/synApps/support/"

if [[ \"${ACTION}\" == \"stop\" ]]; then

    gnome-terminal --tab --title "txmOptics IOC" -- bash -c "
        ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            cd $WORK_DIR/txmoptics/iocBoot/iocTXMOptics/; \
            pkill -9 txmOpticsApp; \
            ./start_IOC;\
            bash
        ';
    "
    gnome-terminal --tab --title "tomoScan IOC" -- bash -c "
        ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            cd $WORK_DIR/tomoscan/iocBoot/iocTomoScan_32ID/; \
            pkill -9 tomoScanApp; \
            bash
        ';
    "
fi
 
if [[ \"${ACTION}\" == \"start\" ]]; then

    #TXM optics server
    echo "Starting txmOptics py server"
    gnome-terminal --tab --title "txmOptics py server" -- bash -c "
        ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            source ~/.bashrc; conda activate $CONDA_ENV; \
            cd $WORK_DIR/txmoptics/iocBoot/iocTXMOptics/; \
            python -i start_txmoptics.py;\
            bash
        ';
    "
    #Tomoscan server
    echo "Starting tomoScan py server"
    gnome-terminal --tab --title "tomoScan py server" -- bash -c "
        ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            source ~/.bashrc; conda activate $CONDA_ENV; \
            cd $WORK_DIR/tomoscan/iocBoot/iocTomoScan_32ID/; \
            python -i start_tomoscan.py;\
            bash
        ';
    "
    echo "Starting tomoScan py server"
    #TXMOptics UI
    gnome-terminal --tab --title "txmOptics UI" -- bash -c "
        ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            source ~/.bashrc; \
            cd $WORK_DIR/txmoptics/iocBoot/iocTXMOptics/; \
            ./start_medm;\
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
    gnome-terminal --tab --title "TXM GUI" -- bash -c "
        # ssh -t ${REMOTE_USER}@${REMOTE_HOST} '
            cd /home/beams/USERTXM/epics/synApps/support/txmoptics/iocBoot/iocTXMOptics/;
            ./start_medm
            bash
        # ';
    "
fi