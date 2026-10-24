#!/bin/bash
# Install the MicroDuck remote-control brain (kick, sit/stand, quack) on the Radxa Cubie A7Z. Run on the Mac:
#
#   microduck-sim/guide/firmware/a7z/install_teleop.sh            # A7Z_HOST=a7z by default (the Mac ssh alias)
#
# What it does, idempotently (rsync --checksum; a second run copies nothing):
#   1. copies walk_wired.py and its whole import closure (mac/, pi/, delay-repair compensation) into the tree the
#      current launch uses: ~/rt/microduck-sim/... (~/duck-run.sh runs walk_wired.py from
#      ~/rt/microduck-sim/guide/firmware/mac with --port /dev/ttyAS2 --baud 500000 --imu-bus 7 --supply bench)
#   2. copies the six 61-input policies (walk/stand/groundpick/sitstand/kick_left/kick_right) and source-lock.json to
#      ~/rt/microduck-sim/hardware-design-20260912/whole-robot-20260912/runtime-overlay/models/
#   3. builds the quack calls (bringup/scripts/build_duck_calls.py: Pollen simulator voices, plus the Commons mallard
#      when MALLARD=path/to/XC62258.ogg is given; 44.1 kHz mono 16-bit WAV, high-passed at 500 Hz, -1 dBFS) and
#      copies them to ~/rt/microduck-sim/guide/firmware/mac/sounds/ (walk_wired.py --sounds default)
#   4. checks on the A7Z: sha256 of every copied file, `aplay -L` has the ALSA default device (the -3 dB softvol
#      ceiling of D-012 lives there), the duck-policy venv imports onnxruntime, the Brain loads all six policies
#      with their metadata checks, walk_wired imports, and the sounds folder has calls
#   5. prints the control-file path walk_wired reads (default --cmd /tmp/duck_cmd.json unless duck-run.sh passes one)
#
# It never moves the robot: no servo traffic, no restart of a running walk_wired.py (the running process keeps the
# old code until ~/duck-run.sh <suffix> starts it again, which comes up in monitor mode). Never copies
# pi/jaw_calibration.json: the jaw marks are taken on the robot and the A7Z copy stays authoritative.
set -euo pipefail

HOST=${A7Z_HOST:-a7z}
HERE=$(cd "$(dirname "$0")" && pwd)
SIM=$(cd "$HERE/../../.." && pwd)                       # .../robotics/microduck-sim
REMOTE_SIM=${REMOTE_SIM:-rt/microduck-sim}             # relative to the A7Z home (/home/radxa)
VENV=${A7Z_VENV:-/home/radxa/.venvs/duck-policy}
MAC_PY=${MAC_PY:-$HOME/.venvs/microduck-walk/bin/python}  # numpy for the call builder
W=hardware-design-20260912/whole-robot-20260912

quiet() { grep -v -E "quantum|store now|upgraded" || true; }   # OpenSSH post-quantum notice on every connection

FILES=(
  guide/firmware/mac/walk_wired.py
  guide/firmware/mac/walk_brain.py
  guide/firmware/mac/jaw_ctl.py
  guide/firmware/mac/duck_sense.py
  guide/firmware/mac/duck_sound.py
  guide/firmware/mac/hold.py
  guide/firmware/pi/battery.py
  guide/firmware/pi/dxl_fast.py
  guide/firmware/pi/jaw_limits.py
  guide/firmware/pi/jaw_limits.json
  guide/firmware/pi/jaw_pose_caps.json
  guide/firmware/pi/joint_signs.py
  guide/firmware/pi/pi_imu_uart.py
  guide/firmware/pi/stand_pose.py
  guide/firmware/pi/microduck_rt/constants.py
  guide/firmware/pi/microduck_rt/imu_reader.py
  "$W/delay-repair-20260912/compensation.py"
  "$W/runtime-overlay/source-lock.json"
)
for m in walk stand groundpick sitstand kick_left kick_right; do FILES+=("$W/runtime-overlay/models/${m}61.onnx"); done

echo "== local checks"
cd "$SIM"
for f in "${FILES[@]}"; do [ -f "$f" ] || { echo "missing locally: $SIM/$f" >&2; exit 1; }; done
python3 - "$W/runtime-overlay/source-lock.json" "$W/runtime-overlay/models" <<'EOF'
import hashlib, json, os, sys
lock = json.load(open(sys.argv[1]))["models_sha256"]
for name in ("walk61.onnx", "stand61.onnx", "groundpick61.onnx", "sitstand61.onnx", "kick_left61.onnx", "kick_right61.onnx"):
    got = hashlib.sha256(open(os.path.join(sys.argv[2], name), "rb").read()).hexdigest()
    if lock.get(name) != got:
        sys.exit(f"{name}: sha256 {got} does not match source-lock.json {lock.get(name)}")
print("policies match source-lock.json")
EOF
command -v ffmpeg >/dev/null || { echo "ffmpeg is needed on the Mac to build the calls (brew install ffmpeg)" >&2; exit 1; }

echo "== building quack calls"
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/duck_sounds.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT
"$MAC_PY" bringup/scripts/build_duck_calls.py "${MALLARD:--}" microduck-simulator/app/public/assets/voices "$STAGE/sounds"
NCALLS=$(ls "$STAGE/sounds"/*.wav | wc -l | tr -d ' ')

echo "== reaching $HOST"
if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "$HOST" true 2> >(quiet >&2); then
  echo "cannot reach $HOST over ssh; nothing was copied" >&2
  exit 2
fi

echo "== copying (rsync --checksum; listed lines are files that changed)"
ssh "$HOST" "mkdir -p '$REMOTE_SIM/guide/firmware/mac/sounds'" 2> >(quiet >&2)
rsync -a --checksum --relative --itemize-changes "${FILES[@]}" "$HOST:$REMOTE_SIM/" 2> >(quiet >&2)
# no -t: the calls are rebuilt with fresh mtimes every run; content decides (--checksum), so unchanged calls stay quiet
rsync -rlp --checksum --delete --itemize-changes "$STAGE/sounds/" "$HOST:$REMOTE_SIM/guide/firmware/mac/sounds/" 2> >(quiet >&2)
rsync -p --checksum --itemize-changes "$HERE/duck-run.sh" "$HOST:duck-run.sh" 2> >(quiet >&2)  # the launcher the app runs

echo "== verifying sha256 on $HOST"
MANIFEST="$STAGE/manifest.sha256"
shasum -a 256 "${FILES[@]}" > "$MANIFEST"
(cd "$STAGE" && shasum -a 256 sounds/*.wav | sed 's#  sounds/#  guide/firmware/mac/sounds/#') >> "$MANIFEST"
if ! ssh "$HOST" "cd '$REMOTE_SIM' && sha256sum --quiet -c -" < "$MANIFEST" 2> >(quiet >&2); then
  echo "sha256 mismatch on $HOST (lines above)" >&2
  exit 3
fi
echo "all $(wc -l < "$MANIFEST" | tr -d ' ') files match ($NCALLS calls)"

echo "== checks on $HOST"
ssh "$HOST" "VENV='$VENV' REMOTE_SIM='$REMOTE_SIM' bash -s" 2> >(quiet >&2) <<'EOF'
set -u
fail=0
if aplay -L 2>/dev/null | grep -qx default; then
  echo "aplay: ALSA default device present"
  ceiling=$(grep -h "max_dB" /etc/asound.conf 2>/dev/null | tr -s ' \t' ' ' || true)
  echo "aplay: /etc/asound.conf${ceiling:+ }${ceiling:- has no max_dB line (check the D-012 -3 dB ceiling)}"
else
  echo "aplay: NO default device in aplay -L"; fail=1
fi
cd "$HOME/$REMOTE_SIM/guide/firmware/mac" || exit 1
"$VENV/bin/python" - <<'PY' || fail=1
import glob, os, onnxruntime
print("venv: onnxruntime", onnxruntime.__version__)
import walk_wired, walk_brain
b = walk_brain.Brain(os.path.join(walk_wired.WHOLE, "runtime-overlay", "models"))
print("brain: policies loaded:", ", ".join(sorted(b.sessions)))
missing = {"walk", "stand", "groundpick", "sitstand", "kick_left", "kick_right"} - set(b.sessions)
assert not missing, f"missing policies {missing}"
print("sounds:", len(glob.glob("sounds/*.wav")), "calls in", os.path.abspath("sounds"))
print("jaw calibration:", "present" if os.path.exists("../pi/jaw_calibration.json") else "MISSING (quack moves no jaw until marked)")
PY
cmdarg=$(grep -o -- '--cmd [^ ]*' "$HOME/duck-run.sh" 2>/dev/null || true)
if [ -n "$cmdarg" ]; then
  echo "control file: ${cmdarg#--cmd } (passed by ~/duck-run.sh)"
elif [ -f "$HOME/duck-run.sh" ]; then
  echo "control file: /tmp/duck_cmd.json (walk_wired default; ~/duck-run.sh passes no --cmd and writes {\"mode\": \"monitor\"} there at start)"
else
  echo "control file: /tmp/duck_cmd.json (walk_wired default); no ~/duck-run.sh found"
fi
if pgrep -f "python walk_wired.py" >/dev/null; then
  echo "walk_wired.py is running with the old code: it picks the new code up at the next ~/duck-run.sh <suffix>"
fi
exit $fail
EOF
echo "== done"
