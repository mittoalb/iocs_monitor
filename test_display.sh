# Find display(s) that belong to this user
for sock in /tmp/.X11-unix/X*; do
    num="${sock##*/X}"
    if [ -O "$sock" ]; then  # owned by this user
        echo $num
	export DISPLAY=":$num"
        break
    fi
done

