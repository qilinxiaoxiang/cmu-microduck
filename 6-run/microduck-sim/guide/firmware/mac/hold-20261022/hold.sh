#!/bin/bash
# Head-pad and lift-by-the-head data session from the Mac (2026-10-22).
#   bash hold.sh [args]        copy hold_session.py + hold.py to ~/duck/ on the A7Z, then run the guided session there
#                              (args go to hold_session.py; paths are on the A7Z, relative to its home, e.g.
#                              --log duck-logs/duck_wired_log_hold1022a.jsonl)
#   bash hold.sh pull [SUFFIX] copy the newest tick log (gzipped) and its label file into data/ here
# Sends no command to the robot. The session writes only its label file and the hold file ~/.duck_hold.json.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
if [ "${1:-}" = pull ]; then
  if [ -n "${2:-}" ]; then
    SUFFIX=$2
  else
    SUFFIX=$(ssh a7z 'basename "$(ls -t ~/duck-logs/duck_wired_log_*.jsonl | head -1)" .jsonl')
    SUFFIX=${SUFFIX#duck_wired_log_}
  fi
  mkdir -p "$HERE/data"
  ssh a7z "gzip -c ~/duck-logs/duck_wired_log_$SUFFIX.jsonl" > "$HERE/data/duck_wired_log_$SUFFIX.jsonl.gz"
  rsync -a "a7z:duck-logs/hold_labels_$SUFFIX.jsonl" "$HERE/data/" || echo "no label file hold_labels_$SUFFIX.jsonl on the A7Z"
  ls -l "$HERE/data/"*"$SUFFIX"*
  echo "next: python3 $HERE/hold_analyze.py $HERE/data/duck_wired_log_$SUFFIX.jsonl.gz $HERE/data/hold_labels_$SUFFIX.jsonl"
  exit 0
fi
ssh a7z 'mkdir -p ~/duck'
rsync -a --checksum "$HERE/hold_session.py" "$HERE/../hold.py" a7z:duck/
# [w] keeps pgrep from matching the remote shell that runs this very command line
pgrep_out=$(ssh a7z 'pgrep -f "[w]alk_wired.py" || true')
[ -n "$pgrep_out" ] || { echo "walk_wired.py is not running on the A7Z: start it first (ssh a7z '~/duck-run.sh <suffix>')"; exit 1; }
ARGS=""
[ $# -eq 0 ] || ARGS=$(printf ' %q' "$@")
ssh -t a7z "python3 ~/duck/hold_session.py$ARGS"
