#!/bin/bash
# MicroDuck head camera stream: rpicam-vid as a TCP listener on port 8554 (one client at a time).
# Started by duck-cam.service; a client disconnect ends rpicam-vid, and systemd restarts it after RestartSec.
#
# Stop for one session:   sudo systemctl stop duck-cam.service
# Disable on boot:        sudo systemctl disable --now duck-cam.service
# Re-enable:              sudo systemctl enable --now duck-cam.service
# Watch:                  journalctl -u duck-cam.service -f
#
# Settings (see mac/CAMERA.md for the measured numbers):
#   --mode 2304:1296:10   full-sensor 2x2-binned mode; the default 1536x864 mode crops to the centre 2/3 of the FOV
#   --flicker-period 8333 cancels 60 Hz mains flicker (the LED lighting gave pink/green bands without it)
#   640x480 @ 10 fps, H.264 baseline, PPS/SPS inline with every I frame (every 10th frame) so a late client can decode
#   (no --no-raw: it overrides --mode and the sensor silently falls back to the cropped 1536x864 mode)
set -u
CODEC="${DUCK_CAM_CODEC:-h264}"
PORT="${DUCK_CAM_PORT:-8554}"
ARGS=(--nopreview -t 0 --listen -o "tcp://0.0.0.0:${PORT}"
      --mode 2304:1296:10 --width 640 --height 480 --framerate 10
      --flicker-period 8333 --denoise cdn_off
      --codec "$CODEC")
if [ "$CODEC" = "h264" ]; then
    ARGS+=(--inline --intra 10 --profile baseline --level 4)
fi
exec rpicam-vid "${ARGS[@]}"
