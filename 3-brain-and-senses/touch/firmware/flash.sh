#!/bin/sh
# Compile touch_xiao and flash it to the XIAO ESP32-S3 on the first /dev/cu.usbmodem* port.
# The Arduino ctags 5.8 binary is x86-only; the build uses Homebrew universal-ctags instead (brew install universal-ctags).
set -e
cd "$(dirname "$0")"
FQBN=esp32:esp32:XIAO_ESP32S3   # USB CDC on boot stays at its default (enabled)
PORT=$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)
[ -n "$PORT" ] || { echo "No /dev/cu.usbmodem* port: plug the XIAO into the Mac with a data USB-C cable." >&2; exit 1; }
arduino-cli compile --fqbn "$FQBN" --build-property "tools.ctags.path=/opt/homebrew/bin" --output-dir touch_xiao/build touch_xiao
arduino-cli upload --fqbn "$FQBN" -p "$PORT" --input-dir touch_xiao/build touch_xiao
echo "Flashed $PORT"
