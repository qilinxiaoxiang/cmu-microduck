#!/bin/bash
# start the onboard MicroDuck brain (monitor mode, torque untouched); logs persist in ~/duck-logs
# Installed to ~/duck-run.sh on the A7Z by install_teleop.sh; the app's duck-command.py runs it as ~/duck-run.sh app<MMDD-HHMMSS>.
suf=${1:?suffix}
# a running brain is stopped first; the 1 s wait (its servo bus and log closing) only when there was one
pkill -f "^/home/radxa/.venvs/duck-policy/bin/python walk_wired.py" && sleep 1
mkdir -p ~/duck-logs
echo "{\"mode\": \"monitor\"}" > /tmp/duck_cmd.json
cd ~/rt/microduck-sim/guide/firmware/mac
setsid nohup /home/radxa/.venvs/duck-policy/bin/python walk_wired.py --port /dev/ttyAS2 --baud 500000 --imu-bus 7 --supply bench \
  --log ~/duck-logs/duck_wired_log_$suf.jsonl > ~/duck-logs/duck_wired_$suf.out 2>&1 < /dev/null &
