# 2. Servos and the OpenRB-150

Fifteen ROBOTIS XL330-M288-T servos on one Dynamixel bus, driven by an OpenRB-150 that sits in the rear pack. The OpenRB runs `firmware/openrb_dual_host.ino`: it is a plain bridge with two hosts, the USB port (a Mac during bring-up and calibration) and the J12 UART (the head computer when the robot runs on its own). Whoever sends a packet gets the answer; nothing on the board plans motion.

## IDs and roles

IDs 1 to 5 are the right leg from the ground up: 1 ankle pitch, 2 knee, 3 hip pitch, 4 hip roll, 5 hip yaw. IDs 6 to 10 are the left leg in the same order: 6 ankle, 7 knee, 8 hip pitch, 9 hip roll, 10 hip yaw. IDs 11 to 15 are the head: 11 head pitch, 12 neck pitch, 13 head yaw, 14 head roll, 15 jaw. `scripts/servo_ids.png` shows them on the robot; `scripts/scan_bus.py` lists which IDs answer and names their roles.

## Chain

Three cables leave the OpenRB: to ID 5 (right leg), to ID 10 (left leg) and to ID 12 (neck), all 180 mm X3P. Right leg: 5 to 4 (180 mm), 4 to 3 (100), 3 to 2 (180), 2 to 1 (180); left leg the same lengths from 10 to 9 to 8 to 7 to 6. Neck: 12 to 11 (100), 11 to 13 (180), 13 to 14 (100), 14 to 15 (180). The build guide (`../docs/MICRODUCK-BUILD.html`, chapter "Wiring") shows each cable in place.

## Setting the servos up, in order

1. Give each servo its ID. Servos from two kits arrive with duplicate IDs; `scripts/assign_ids.py` splits them by unplugging one link, parking the answering servos on temporary IDs, and finalizing to 1 to 15 while you move each joint by hand. It also sets Return Delay Time to 0.
2. Check the voltage limits with `scripts/check_voltage_limit.py`: the XL330's Max Voltage Limit is 70 (7.0 V) and cannot be raised, so the servo rail must stay under it (see `4-power/`). On the bench rail the factory Shutdown value 53 stays.
3. For the battery route only, `scripts/set_shutdown.py` writes Shutdown 52 to every servo (torque off, all 15 answering), which stops a full 2S pack from cutting torque with an input-voltage error. `--restore` puts 53 back.
4. Fit the horns at the calibration poses shown in the build guide. Two horn fits matter more than the others: ID 5 (right hip yaw) must sit so that leg-forward reads near 2048, far from the encoder's 0/4095 seam; `scripts/hip_yaw_check.py` refuses to let the runtime start otherwise, and `scripts/id5_horn_turn.py` is the one-off procedure that turned our shaft half a turn under the horn when it did not. The right hip pitch (ID 3) horn on our robot was refitted on 2026-10-23 and its offset lives in `scripts/joint_signs.py`.
5. `scripts/joint_signs.py` holds this build's signs and offsets between the simulator's joint convention and the servo ticks (neck and head pitch reversed, knees at plus or minus 45 degrees, left ankle at minus 90 degrees). If your horns sit differently, this is the file to change; the standing check below tells you whether you got it right.
6. Stand check: `scripts/stand.py` ramps the robot to the standing pose at P gain 400 with torque on; `scripts/stand_pose.py` is the pose, `scripts/stance_switch.py` steps between stances and logs servo and IMU lag (the robot ends standing, torque on). `scripts/regdump.py` prints every register of one servo when something is odd; `scripts/battery.py` is the voltage guard the runtime shares. `scripts/dxl_fast.py` is the packet helper all of these use.

All scripts run on the Mac over the OpenRB USB cable (`--port` defaults to the first `/dev/cu.usbmodem*`) with `pip install dynamixel-sdk pyserial`, or on the head computer over `/dev/ttyAS2` at 500 kbaud. Only one host may talk at a time.

## Flashing the OpenRB

The board ships with ROBOTIS's `usb_to_dynamixel` sketch, which already works for the Mac-over-USB steps above. Flash `openrb_dual_host.ino` before the head computer takes over the bus. Compile it in the Arduino IDE with the ROBOTIS OpenRB-150 board package, then write the binary with the Arduino bootloader's own tool:

```
bossac --port=cu.usbmodemXXXX -U --offset=0x2000 -e -w -v -R openrb_dual_host.ino.bin
```

Do not add `-i` or `-d`; both wedge the bootloader on this board. Read this before you flash anything: once the OpenRB is inside the torso its RESET button is out of reach, and the bootloader re-enters only on a RESET double-tap (a power cycle clears the flag). An image that hangs before the USB port comes up therefore locks the board out of both USB and J12 until the robot is opened. We did exactly that on 2026-10-18 with an unneeded image. So: flash while the board is still reachable, flash only a binary you have seen run, and check first whether the firmware already on the board does what you need. `openrb_dual_host` serves both hosts at once (USB at 1 Mbaud bus speed, J12 at 500 kbaud), which covers every step in this repository.

Sources: the sketch is ROBOTIS's `usb_to_dynamixel.ino` example (Apache-2.0) with the second host added; the header of `firmware/openrb_dual_host.ino` says what changed.
