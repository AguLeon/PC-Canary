#!/bin/bash

# Run the VNC Server
vncserver -xstartup ~/.vnc/xstartup -geometry 1024x768 :4

# Run the noVNC server (for web inteface)
/opt/noVNC/utils/novnc_proxy \
    --vnc localhost:5904 \
    --listen 0.0.0.0:6080 \
    --web /opt/noVNC > /tmp/novnc.log 2>&1 &

# Run the ollama server
ollama serve > /tmp/ollama.log 2>&1 &
