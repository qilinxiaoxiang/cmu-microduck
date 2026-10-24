#!/bin/sh
# Download the six Pollen Robotics MicroDuck policies the runtime loads and check them against the sha256 values
# recorded in runtime-overlay/source-lock.json. The ONNX files are Pollen's; they are not redistributed here.
#
#   sh 6-run/fetch_policies.sh            # writes runtime-overlay/models/*.onnx
#
# Source: the Hugging Face Space pollen-robotics/microduck-simulator, folder app/public/policies, at the commit that holds the policy files the robot runs
# (836975a, 2026-08-25: the last change to any of the six files). Our names on the left, Pollen's file names on the right.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
DEST="$HERE/microduck-sim/hardware-design-20260912/whole-robot-20260912/runtime-overlay/models"
BASE="https://huggingface.co/spaces/pollen-robotics/microduck-simulator/resolve/836975ab63058b2235fe23878bb86a3e2eee7089/app/public/policies"
mkdir -p "$DEST"
fetch() {
  ours=$1; theirs=$2; want=$3
  out="$DEST/$ours.onnx"
  if [ ! -s "$out" ]; then
    echo "fetching $theirs.onnx -> $ours.onnx"
    curl -fL --retry 3 -o "$out.part" "$BASE/$theirs.onnx"
    mv "$out.part" "$out"
  fi
  got=$(shasum -a 256 "$out" | cut -d' ' -f1)
  if [ "$got" != "$want" ]; then
    echo "sha256 mismatch for $ours.onnx: got $got, want $want (source-lock.json)" >&2
    exit 1
  fi
  echo "ok $ours.onnx $got"
}
fetch stand61      BEST_alpha_stand    1569268713e40deea795dd2922dba50d3621e15a872855408b6b1b125b1c094b
fetch walk61       BEST_alpha_walking  e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c
fetch groundpick61 alpha_ground_pick   ffbf5109982ff999b0ba53afe86b9ae731bbec679d67fb7f8ab4c52152c88872
fetch sitstand61   BEST_alpha_sitstand c6c40e35e726eabd803d633e090d112994f469921152448367953fbaf9799bc8
fetch kick_left61  ball_kick_left      d6928284dccd3dd61e08bf2f760effa74309fbefd97b2b31afb2a60f526d196a
fetch kick_right61 ball_kick_right     147a32c388c6b19111b3ac3b550a9a6dc8b8bf267118af4d8c3712522eedb5af
echo "all six policies present in $DEST"
