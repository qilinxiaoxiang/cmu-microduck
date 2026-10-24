# 6. Run

The runtime that stands and walks the robot, as deployed on 2026-10-23. It is one Python process, `walk_wired.py`, that runs a 50 Hz loop: read the 14 body servos and the IMU, feed Pollen's 61-input ONNX policy, write the goals, and watch the guards. It reads commands from a small JSON file and writes a per-tick log. The same code runs on the A7Z in the head (the robot on its own) or on a Mac over the OpenRB USB cable (bring-up).

## Layout

`microduck-sim/` mirrors the paths the code expects, so copy the whole folder as it is:

- `guide/firmware/mac/`: `walk_wired.py` (entry point, transport, guards, quack, hold), `walk_brain.py` (policies, joint convention, heading hold, kick, sit, groundpick), `jaw_ctl.py` (the jaw servo, ID 15, in current-based position mode), `hold.py` (graded hold from the touch pads and leg load), `duck_sound.py`, `duck_sense.py` (read-only pose reader while no brain runs), `robot_state_check.py` (reads the servo rail, IMU rate and read drops the way the project's state file records them).
- `guide/firmware/pi/`: shared helpers: `dxl_fast.py` (packets), `battery.py` (voltage guard), `joint_signs.py` (this build's signs and offsets), `stand_pose.py`, `jaw_limits.py` with `jaw_limits.json` and `jaw_pose_caps.json` (how far the jaw may open in each head pose), `pi_imu_uart.py`, `microduck_rt/` (IMU reader and constants from AI-FanGe's runtime).
- `hardware-design-20260912/whole-robot-20260912/delay-repair-20260912/compensation.py` and `runtime-overlay/source-lock.json`: the delay compensation module (off by default) and the record of where every policy and source file came from, with sha256.
- `runtime-overlay/models/`: empty in git. Run `fetch_policies.sh` to download Pollen's six policies and check their hashes.

Policies, all from Pollen's microduck-simulator: `walk61` (BEST_alpha_walking), `stand61` (BEST_alpha_stand), `groundpick61` (alpha_ground_pick), `sitstand61` (BEST_alpha_sitstand), `kick_left61` and `kick_right61` (ball_kick_left/right). They are Pollen's work under their repository's terms; this repository only tells you where to get the exact files the robot runs.

## Install

Python 3.11 or later in a venv with `onnxruntime numpy pyserial dynamixel-sdk smbus2` (the A7Z venv is `/home/radxa/.venvs/duck-policy`). On the A7Z, `3-brain-and-senses/a7z/install_teleop.sh` does the copy from a Mac, builds the quack calls into `guide/firmware/mac/sounds/`, and checks the venv, the ALSA default device and that the brain loads all six policies. `3-brain-and-senses/a7z/duck-run.sh <suffix>` then starts the brain in monitor mode:

```
python walk_wired.py --port /dev/ttyAS2 --baud 500000 --imu-bus 7 --supply bench --log ~/duck-logs/duck_wired_log_<suffix>.jsonl
```

On a Mac over USB the port is the `/dev/cu.usbmodem*` of the OpenRB at the default 1 Mbaud, and the IMU must come from the head over J12 (`pi_imu_uart.py` running there) or from a BNO085 on a USB I2C adapter.

## Commands

Write JSON to `/tmp/duck_cmd.json`; the loop reads it every tick. `{"mode": "monitor"}` reads only and never writes torque. `{"mode": "stand"}` writes the present positions as goals, enables torque, and ramps to the standing pose at P gain 400 (open loop). `{"mode": "walk", "vx": 0.25, "vy": 0, "vtheta": 0}` runs stand61 at zero command and walk61 when a velocity is given, P gain 200, with the heading hold (a learned yaw trim in `~/.duck_yaw_trim.json` plus a PI loop on the IMU heading, turn command capped at 2.0 rad/s). `"for_s": 7` stops the walk 7 s after the command; rewriting every 0.3 s with `"for_s": 0.6` gives hold-to-walk. `{"mode": "groundpick", "phase": 0.33}` crouches with Pollen's ground-pick policy. `{"mode": "sit"}`, `{"mode": "kick", "foot": "left", "id": 1}` use the other two policies. `"quack": N` (a new counter value) plays a call, opens the jaw and nods the head when a policy can rebalance under it. `"jaw": 20`, `"jaw": "grip"`, `"jaw_torque": false`, `"jaw_mark": "closed"` or `"open"` control and calibrate the jaw; no jaw goal is written until both marks exist in `pi/jaw_calibration.json`. `{"mode": "off"}` is the only command that releases torque (and reboots any servo with a latched error).

The graded hold (`hold.py`) is on when `~/.duck_hold.json` says `{"on": true, "cal": {...}}` with a leg-load calibration: a hand on the head pads lowers the policy's authority and the leg gains gradually, so you can pick the robot up mid-walk and set it down standing. `guide/firmware/mac/hold-20261022/hold_session.py` (run on the A7Z beside the brain; `hold.sh` starts it) shows the pads and leg currents live, lets you label lift trials, and writes the calibration into the hold file; it never sends a command to the robot. On 2026-10-23 the hold kept 6 of 6 lifts.

## First run, in order

1. Power the robot lying on its side (it powers up on its side; nobody lifts it before torque is on). The servo rail reads 7.0 to 7.3 V, the A7Z boots, 15 of 15 servos answer `2-servos-openrb/scripts/scan_bus.py`, and `hip_yaw_check.py` passes.
2. Start the brain in monitor mode (`duck-run.sh`). Watch the log: IMU samples arrive every tick, 50 per second, with about 4 % servo read drops and no hardware error flags.
3. `{"mode": "stand"}`: the servos hold where they are, then ramp to the stance. Right the robot by hand onto its feet.
4. `{"mode": "walk", "vx": 0, "vy": 0, "vtheta": 0}`: stand61 balances. Nudge it; it should recover.
5. `{"mode": "walk", "vx": 0.25, "vy": 0, "vtheta": 0, "for_s": 4}`: a 4 s walk at 0.25 m/s, the speed the robot was walked at on 2026-10-23. Stand behind it. A tilt over 60 degrees or an action over the limit stops the walk into stand61.
6. `{"mode": "off"}` only when the robot is held or lying down.

## Safety notes

Torque stays on until you say otherwise: stopping the brain process leaves the servos holding their last goals, a reboot of the A7Z keeps the goals too, and no timer releases them. Hold the robot or lay it down before `off`. The servos' overload and overheating shutdowns stay armed; a latched error freezes the policy on its last goals. Never run a policy mode at a loop rate under 49 ticks per second (see the thermal limit in `3-brain-and-senses/`): walk61 diverged at 36 Hz. The open-loop stand mode cannot rebalance: do not quack or push in it.
